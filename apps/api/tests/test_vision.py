import asyncio
import base64
import json
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from fastapi import UploadFile

from app import vision
from app.errors import ApiError

pytest.importorskip("PIL")
pytest.importorskip("meta_sam_parser")

MASK_TEXT = "<0f>0<|box;x1=1;y1=2;x2=4;y2=5;w=20;h=10|><|mask;x=0;y=0;data=2,2,!!!!!&MoT/:|>"


@pytest.fixture
def settings(monkeypatch):
    settings = SimpleNamespace(
        yolo_model_path="models/best.pt", model_api_key="test-key", sam_timeout_seconds=1,
    )
    monkeypatch.setattr(vision, "get_settings", lambda: settings)
    return settings


def photo():
    from PIL import Image

    data = BytesIO()
    Image.new("RGB", (20, 10)).save(data, format="PNG")
    # Photo validation leaves the upload at EOF before inference.
    return UploadFile(data, filename="photo.png")


def detection():
    return {"object_id": "0", "class_id": 0, "label": "crack", "confidence": 0.9,
            "bbox": [1, 2, 5, 6], "image_size": [20, 10], "source": "yolo",
            "segmentation_status": "pending", "mask": None}


def mock_api(monkeypatch, text, *, complete=True, status=200):
    captured = []
    lane = {"item_id": "item-1", "output_index": 0, "content_index": 0}
    events = [
        {"type": "response.output_text.delta", **lane, "delta": text[:20]},
        {"type": "response.output_text.delta", **lane, "delta": text[20:]},
        {"type": "response.output_text.done", **lane, "text": text},
    ]
    if complete:
        events.append({"type": "response.completed"})
    body = ": heartbeat\n\n" + "".join("data: " + json.dumps(e) + "\n\n" for e in events)

    def handle(request):
        captured.append(request)
        return httpx.Response(status, text=body, headers={"Content-Type": "text/event-stream"})

    client = httpx.AsyncClient
    monkeypatch.setattr(vision.httpx, "AsyncClient", lambda **kwargs: client(
        transport=httpx.MockTransport(handle), **kwargs,
    ))
    return captured


def test_sam_box_request_parses_real_stream_and_decodes_mask(monkeypatch, settings):
    from PIL import Image

    # A 2x2 one-bit wire mask with raster [0, 1, 1, 0].
    captured = mock_api(monkeypatch, MASK_TEXT)
    masks = asyncio.run(vision._segment(Image.new("RGB", (20, 10)), [detection()]))
    assert masks["0"]["size"] == (2, 2)
    assert masks["0"]["counts"] == "121"
    assert masks["0"]["svg_path"]
    assert masks["0"]["bounds"] == {"left": 1, "top": 2, "right": 5, "bottom": 6}
    request = captured[0]
    assert str(request.url) == "https://api.meta.ai/v1/responses"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    content = payload["input"][0]["content"]
    assert content[0]["text"] == "<0f>0<|box;x1=1;y1=2;x2=4;y2=5;w=20;h=10|>"
    from PIL import Image as PILImage
    image_data = base64.b64decode(content[1]["image_url"].split(",", 1)[1])
    assert PILImage.open(BytesIO(image_data)).size == (20, 10)


@pytest.mark.parametrize("consent,key,status", [
    (False, "test-key", "skipped_no_consent"), (True, None, "unavailable"),
])
def test_no_external_call_without_consent_or_key(monkeypatch, settings, consent, key, status):
    settings.model_api_key = key
    monkeypatch.setattr(vision, "_detect", lambda *_: [detection()])
    async def forbidden(*_):
        pytest.fail("Photo was sent without consent or key")
    monkeypatch.setattr(vision, "_segment", forbidden)
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], consent)
    assert result["applied"] is True
    assert result["source"] == "yolo"
    assert result["photos"][0]["detections"][0]["segmentation_status"] == status
    upload.file.close()


@pytest.mark.parametrize("text,complete,http_status,expected", [
    ("", True, 200, "no_mask"),
    ("", False, 200, "failed"),
    ("bad mask", True, 200, "failed"),
    ("", True, 429, "failed"),
    ("", True, 500, "failed"),
])
def test_empty_and_failed_sam_keep_yolo_detections(
    monkeypatch, settings, text, complete, http_status, expected,
):
    monkeypatch.setattr(vision, "_detect", lambda *_: [detection()])
    mock_api(monkeypatch, text, complete=complete, status=http_status)
    upload = photo()
    result = vision.analyze_photos([upload], ["closeup"], True)
    detected = result["photos"][0]["detections"][0]
    assert detected["label"] == "crack"
    assert detected["confidence"] == 0.9
    assert detected["segmentation_status"] == expected
    assert detected["mask"] is None
    upload.file.close()


def test_no_detections_skip_sam(monkeypatch, settings):
    monkeypatch.setattr(vision, "_detect", lambda *_: [])
    async def forbidden(*_):
        pytest.fail("SAM called without detections")
    monkeypatch.setattr(vision, "_segment", forbidden)
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["detections"] == []
    upload.file.close()


def test_corrupt_image_rejected_before_detection(settings):
    upload = UploadFile(BytesIO(b"\x89PNG\r\n\x1a\n" + b"broken"))
    with pytest.raises(ApiError) as error:
        vision.analyze_photos([upload], ["overview"], True)
    assert error.value.status_code == 422
    upload.file.close()


def test_exif_orientation_is_applied_before_detection(monkeypatch, settings):
    from PIL import Image

    data = BytesIO()
    image = Image.new("RGB", (20, 10))
    exif = Image.Exif()
    exif[274] = 6
    image.save(data, format="JPEG", exif=exif)
    upload = UploadFile(data)
    sizes = []
    def detect(image, _):
        sizes.append(image.size)
        return []
    monkeypatch.setattr(vision, "_detect", detect)
    vision.analyze_photos([upload], ["overview"], True)
    assert sizes == [(10, 20)]
    upload.file.close()


def test_api_saves_real_detection_and_mask_with_sample_diagnosis(
    monkeypatch, settings, client, user_factory, token_for, record_factory,
):
    monkeypatch.setattr("app.records.get_settings", lambda: settings)
    monkeypatch.setattr(vision, "_detect", lambda *_: [detection()])
    mock_api(monkeypatch, MASK_TEXT)
    user_id = user_factory()
    record_id = record_factory(user_id)["record_id"]
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    upload = photo()
    data = upload.file.getvalue()
    upload.file.close()
    response = client.post(
        f"/records/{record_id}/analyze", headers=headers,
        data={"photo_roles": "overview", "external_analysis_consent": "true",
              "location": "안방", "material": "벽지"},
        files=[("photos", ("photo.png", data, "image/png"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "yolo_sam"
    assert body["diagnosis"]["source"] == "sample"
    detected = body["photo_analysis"]["photos"][0]["detections"][0]
    assert detected["segmentation_status"] == "completed"
    assert detected["mask"]["counts"] == "121"
    assert detected["mask"]["svg_path"]
    detail = client.get(f"/records/{record_id}", headers=headers).json()
    assert detail["photo_observations"] == body["photo_analysis"]
    def unavailable(*_):
        raise ApiError(503, "yolo_unavailable", "하자 탐지 모델을 실행할 수 없습니다.")
    monkeypatch.setattr(vision, "_detect", unavailable)
    failed = client.post(
        f"/records/{record_id}/analyze", headers=headers,
        data={"photo_roles": "overview", "external_analysis_consent": "true",
              "location": "바뀐 위치", "material": "벽지"},
        files=[("photos", ("photo.png", data, "image/png"))],
    )
    assert failed.status_code == 503
    assert client.get(f"/records/{record_id}", headers=headers).json() == detail


def test_sam_timeout_keeps_local_detection(monkeypatch, settings):
    monkeypatch.setattr(vision, "_detect", lambda *_: [detection()])
    client = httpx.AsyncClient
    def timeout(request):
        raise httpx.ReadTimeout("test timeout", request=request)
    monkeypatch.setattr(vision.httpx, "AsyncClient", lambda **kwargs: client(
        transport=httpx.MockTransport(timeout), **kwargs,
    ))
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["detections"][0]["segmentation_status"] == "failed"
    upload.file.close()
