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
        llm_api_key="test-key", llm_model="vision-model", vision_llm_model=None,
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
    monkeypatch.setattr(
        vision.llm, "generate_json",
        lambda *a, **k: observation(),
    )
    async def forbidden(*_):
        pytest.fail("SAM called without detections")
    monkeypatch.setattr(vision, "_segment", forbidden)
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["detections"] == []
    assert result["photos"][0]["status"] == "analyzed"
    assert result["photos"][0]["source"] == "vision_llm"
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
    monkeypatch.setattr(vision.llm, "generate_json", lambda *a, **k: observation())
    vision.analyze_photos([upload], ["overview"], True)
    assert sizes == [(10, 20)]
    upload.file.close()


def diagnosis_result():
    return {
        "observations": "사진과 입력에서 곰팡이 흔적을 확인했습니다.",
        "suspected_types": ["곰팡이"],
        "severity_score": 55,
        "severity_level": "medium",
        "reason": "표면 곰팡이 의심",
        "causes": ["결로 가능성"],
        "estimation_notice": "AI 추정 안내",
        "recommended_action": "inspection",
        "care_steps": ["환기"],
        "supplies": ["마스크"],
        "prevention_tips": ["환기 유지"],
        "unknowns": ["누수 여부"],
        "work_type_id": None,
        "work_type_reason": "원인 점검 필요",
        "source": "llm",
    }


def test_api_saves_real_detection_and_mask_with_llm_diagnosis(
    monkeypatch, settings, client, user_factory, token_for, record_factory,
):
    from app import llm

    monkeypatch.setattr("app.records.get_settings", lambda: settings)
    monkeypatch.setattr(vision, "_detect", lambda *_: [detection()])
    monkeypatch.setattr(
        "app.diagnosis.generate_diagnosis", lambda *_: diagnosis_result()
    )
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
    assert body["diagnosis"]["source"] == "llm"
    detected = body["photo_analysis"]["photos"][0]["detections"][0]
    assert detected["label"] == "crack"
    assert detected["area_ratio"] == pytest.approx(0.5 * 16 / 200)
    assert detected["segmentation_status"] == "completed"
    assert detected["mask"]["counts"] == "121"
    assert detected["mask"]["svg_path"]
    assert "_area_ratio" not in detected["mask"]
    detail = client.get(f"/records/{record_id}", headers=headers).json()
    assert detail["photo_observations"] == body["photo_analysis"]

    def broken(*_):
        raise llm.LlmError

    monkeypatch.setattr("app.diagnosis.generate_diagnosis", broken)
    failed = client.post(
        f"/records/{record_id}/analyze", headers=headers,
        data={"photo_roles": "overview", "external_analysis_consent": "true",
              "location": "바뀐 위치", "material": "벽지"},
        files=[("photos", ("photo.png", data, "image/png"))],
    )
    assert failed.status_code == 502
    assert client.get(f"/records/{record_id}", headers=headers).json() == detail


def observation(**overrides):
    payload = {
        "suspected_types": ["mold"],
        "summary": "창틀 아래 검은 얼룩",
        "approximate_location": "창틀 아래",
        "unreadable_reason": None,
    }
    payload.update(overrides)
    return payload


def test_vision_llm_observes_only_photos_without_detections(monkeypatch, settings):
    calls = []

    def observe(prompt, **kwargs):
        calls.append(kwargs["model"])
        return observation()

    monkeypatch.setattr(vision, "_detect", lambda *_: [])
    monkeypatch.setattr(vision.llm, "generate_json", observe)
    uploads = [photo(), photo()]
    result = vision.analyze_photos(uploads, ["overview", "closeup"], True)
    assert calls == ["vision-model", "vision-model"]
    assert result["source"] == "vision_llm"
    assert result["applied"] is True
    assert [p["status"] for p in result["photos"]] == ["analyzed", "analyzed"]
    assert result["photos"][0]["vision_observation"] == {
        "suspected_types": ["곰팡이"],
        "summary": "창틀 아래 검은 얼룩",
        "approximate_location": "창틀 아래",
        "unreadable_reason": None,
    }
    for upload in uploads:
        upload.file.close()


def test_vision_llm_falls_back_when_yolo_fails(monkeypatch, settings):
    def unavailable(*_):
        raise ApiError(503, "yolo_unavailable", "하자 탐지 모델을 실행할 수 없습니다.")

    monkeypatch.setattr(vision, "_detect", unavailable)
    monkeypatch.setattr(vision.llm, "generate_json", lambda *a, **k: observation())
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["source"] == "vision_llm"
    assert result["photos"][0]["status"] == "analyzed"
    upload.file.close()


def test_vision_llm_failure_marks_photo_failed(monkeypatch, settings):
    from app import llm

    monkeypatch.setattr(vision, "_detect", lambda *_: [])

    def broken(*_a, **_k):
        raise llm.LlmError

    monkeypatch.setattr(vision.llm, "generate_json", broken)
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["status"] == "failed"
    assert result["photos"][0]["source"] == "vision_llm"
    assert result["photos"][0]["vision_observation"] is None
    upload.file.close()


def test_unreadable_vision_observation_marks_photo_failed(monkeypatch, settings):
    monkeypatch.setattr(vision, "_detect", lambda *_: [])
    monkeypatch.setattr(
        vision.llm, "generate_json",
        lambda *a, **k: observation(summary="", unreadable_reason="흐림"),
    )
    upload = photo()
    result = vision.analyze_photos([upload], ["overview"], True)
    assert result["photos"][0]["status"] == "failed"
    assert result["photos"][0]["vision_observation"]["unreadable_reason"] == "흐림"
    upload.file.close()


def test_mixed_yolo_and_vision_sources_are_reported(monkeypatch, settings):
    settings.model_api_key = None
    results = iter([[detection()], []])
    monkeypatch.setattr(vision, "_detect", lambda *_: next(results))
    monkeypatch.setattr(vision.llm, "generate_json", lambda *a, **k: observation())
    uploads = [photo(), photo()]
    result = vision.analyze_photos(uploads, ["overview", "closeup"], True)
    assert [p["source"] for p in result["photos"]] == ["yolo", "vision_llm"]
    assert result["source"] == "yolo_vision_llm"
    for upload in uploads:
        upload.file.close()


def test_yolo_path_without_llm_key_is_unavailable(monkeypatch, settings):
    settings.llm_api_key = None
    upload = photo()
    with pytest.raises(ApiError) as error:
        vision.analyze_photos([upload], ["overview"], True)
    assert error.value.status_code == 503
    assert error.value.code == "llm_unavailable"
    upload.file.close()


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
