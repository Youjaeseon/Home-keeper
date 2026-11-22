import asyncio
import base64
import threading

import httpx

from app.main import app
from conftest import auth_headers

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6n0sAAAAASUVORK5CYII="
)
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _analyze(
    client,
    token,
    record_id,
    *,
    photos=None,
    roles=None,
    consent=False,
    location="안방 창틀 아래",
    material="실리콘",
    symptoms="검은 곰팡이 의심 얼룩이 번져 있어요",
):
    photos = photos if photos is not None else [(PNG_1X1, "overview.png", "image/png")]
    roles = roles if roles is not None else ["overview" for _ in photos]
    files = [
        ("photos", (filename, data, content_type))
        for data, filename, content_type in photos
    ]
    data = {
        "photo_roles": roles,
        "external_analysis_consent": "true" if consent else "false",
        "location": location,
        "material": material,
    }
    if symptoms is not None:
        data["symptoms"] = symptoms
    return client.post(
        f"/records/{record_id}/analyze",
        headers=auth_headers(token),
        data=data,
        files=files,
    )


def _get_record(client, token, record_id):
    return client.get(f"/records/{record_id}", headers=auth_headers(token))


def test_analyze_one_photo_stores_sample_diagnosis_and_material(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = _analyze(client, token, record_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "sample"
    assert body["record_id"] == record_id
    assert body["input_revision"] == 1
    assert body["diagnosis_generation"] == 1
    assert body["photo_analysis"]["applied"] is False
    assert body["photo_analysis"]["source"] == "sample"
    assert body["photo_analysis"]["notice"]
    assert body["photo_analysis"]["photos"] == [
        {
            "role": "overview",
            "status": "not_analyzed",
            "source": "sample",
            "detections": [],
            "vision_observation": None,
        }
    ]
    assert "bbox" not in response.text
    assert "confidence" not in response.text

    diagnosis = body["diagnosis"]
    assert diagnosis["source"] == "sample"
    assert 0 <= diagnosis["severity_score"] <= 100
    assert diagnosis["severity_level"] in {"low", "medium", "high"}
    assert diagnosis["reason"]
    assert diagnosis["causes"]
    assert "샘플" in diagnosis["estimation_notice"]
    assert diagnosis["recommended_action"] in {
        "self_care",
        "inspection",
        "provider_consult",
    }
    assert diagnosis["care_steps"]
    assert diagnosis["supplies"]
    assert diagnosis["prevention_tips"]
    assert diagnosis["unknowns"]
    assert diagnosis["work_type_id"] is None
    assert diagnosis["work_type_reason"]

    detail = _get_record(client, token, record_id).json()
    assert detail["location"] == "안방 창틀 아래"
    assert detail["material"] == "실리콘"
    assert detail["symptoms"] == "검은 곰팡이 의심 얼룩이 번져 있어요"
    assert detail["input_revision"] == 1
    assert detail["photo_observations"] == body["photo_analysis"]
    assert detail["diagnosis"]["diagnosis"] == diagnosis
    assert detail["diagnosis"]["input_revision"] == 1
    assert detail["diagnosis"]["generation"] == 1
    assert detail["diagnosis"]["is_current"] is True
    assert "bbox" not in str(detail["photo_observations"])
    assert "confidence" not in str(detail["photo_observations"])


def test_analyze_two_photos_keeps_roles_without_detections(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = _analyze(
        client,
        token,
        record_id,
        photos=[
            (PNG_1X1, "overview.png", "image/png"),
            (PNG_1X1, "closeup.png", "image/png"),
        ],
        roles=["overview", "closeup"],
        symptoms=None,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [photo["role"] for photo in body["photo_analysis"]["photos"]] == [
        "overview",
        "closeup",
    ]
    assert all(
        photo["status"] == "not_analyzed"
        and photo["source"] == "sample"
        and photo["detections"] == []
        for photo in body["photo_analysis"]["photos"]
    )
    detail = _get_record(client, token, record_id).json()
    assert detail["symptoms"] is None
    assert detail["material"] == "실리콘"


def test_analyze_rejects_other_users_record(
    client, user_factory, token_for, record_factory
):
    owner_id = user_factory()
    other_id = user_factory()
    record_id = record_factory(owner_id)["record_id"]

    response = _analyze(client, token_for(other_id), record_id)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"

    owner_detail = _get_record(client, token_for(owner_id), record_id).json()
    assert owner_detail["material"] is None
    assert owner_detail["diagnosis"] is None


def test_analyze_rejects_missing_extra_or_invalid_photos(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    assert _analyze(client, token, record_id, photos=[], roles=[]).status_code == 422
    assert (
        _analyze(
            client,
            token,
            record_id,
            photos=[
                (PNG_1X1, "1.png", "image/png"),
                (PNG_1X1, "2.png", "image/png"),
                (PNG_1X1, "3.png", "image/png"),
            ],
            roles=["overview", "closeup", "overview"],
        ).status_code
        == 422
    )
    assert (
        _analyze(
            client,
            token,
            record_id,
            photos=[(PNG_1X1, "overview.png", "image/png")],
            roles=["overview", "closeup"],
        ).status_code
        == 422
    )
    assert (
        _analyze(
            client,
            token,
            record_id,
            photos=[(b"not an image", "bad.txt", "text/plain")],
            roles=["overview"],
        ).status_code
        == 422
    )
    assert (
        _analyze(
            client,
            token,
            record_id,
            photos=[(b"\x89PNG\r\n\x1a\n" + b"0" * MAX_PHOTO_BYTES, "large.png", "image/png")],
            roles=["overview"],
        ).status_code
        == 422
    )

    detail = _get_record(client, token, record_id).json()
    assert detail["material"] is None
    assert detail["photo_observations"] is None
    assert detail["diagnosis"] is None


def test_analyze_rejects_blank_location_or_material(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    assert _analyze(client, token, record_id, location="   ").status_code == 422
    assert _analyze(client, token, record_id, material="").status_code == 422

    detail = _get_record(client, token, record_id).json()
    assert detail["material"] is None
    assert detail["diagnosis"] is None


def test_analyze_same_inputs_does_not_bump_revision(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    first = _analyze(client, token, record_id)
    assert first.status_code == 200, first.text
    second = _analyze(client, token, record_id)
    assert second.status_code == 200, second.text
    assert second.json()["input_revision"] == 1
    assert second.json()["diagnosis_generation"] == 2

    detail = _get_record(client, token, record_id).json()
    assert detail["input_revision"] == 1
    assert detail["diagnosis"]["generation"] == 2
    assert detail["diagnosis"]["is_current"] is True


def test_analyze_input_change_during_generation_returns_409_without_partial_save(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    from app.sample_analysis import build_sample_analysis as real_analysis

    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    started = threading.Event()
    release = threading.Event()

    def slow(**kwargs):
        started.set()
        if not release.wait(10):
            raise AssertionError("test did not release the sample analysis")
        return real_analysis(**kwargs)

    monkeypatch.setattr("app.records.build_sample_analysis", slow)
    form = {
        "photo_roles": ["overview"],
        "external_analysis_consent": "false",
        "location": "안방 창틀 아래",
        "material": "실리콘",
        "symptoms": "검은 곰팡이 의심",
    }

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            pending = asyncio.create_task(
                async_client.post(
                    f"/records/{record_id}/analyze",
                    headers=auth_headers(token),
                    data=form,
                    files=[("photos", ("overview.png", PNG_1X1, "image/png"))],
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 10)
                patched = await async_client.patch(
                    f"/records/{record_id}",
                    headers=auth_headers(token),
                    json={"material": "벽지"},
                )
                assert patched.status_code == 200, patched.text
                assert patched.json()["input_revision"] == 1
            finally:
                release.set()
            return await pending

    response = asyncio.run(scenario())
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "revision_conflict"
    assert response.json()["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert detail["material"] == "벽지"
    assert detail["input_revision"] == 1
    assert detail["photo_observations"] is None
    assert detail["diagnosis"] is None


def test_concurrent_analyze_does_not_mix_inputs_and_diagnosis(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    from app.sample_analysis import build_sample_analysis as real_analysis

    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    locations = ["안방 창틀 아래", "거실 창틀 아래"]
    barrier = threading.Barrier(2, timeout=10)

    def synchronized(**kwargs):
        barrier.wait()
        return real_analysis(**kwargs)

    monkeypatch.setattr("app.records.build_sample_analysis", synchronized)

    async def send(async_client, location):
        return await async_client.post(
            f"/records/{record_id}/analyze",
            headers=auth_headers(token),
            data={
                "photo_roles": ["overview"],
                "external_analysis_consent": "false",
                "location": location,
                "material": "실리콘",
                "symptoms": "검은 곰팡이 의심",
            },
            files=[("photos", ("overview.png", PNG_1X1, "image/png"))],
        )

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            return await asyncio.gather(
                send(async_client, locations[0]),
                send(async_client, locations[1]),
            )

    responses = asyncio.run(scenario())
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    winner_index = next(
        index for index, response in enumerate(responses) if response.status_code == 200
    )
    winner = responses[winner_index]
    loser = responses[1 - winner_index]
    assert winner.json()["input_revision"] == 1
    assert loser.json()["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert detail["location"] == locations[winner_index]
    assert locations[winner_index] in detail["diagnosis"]["diagnosis"]["observations"]
    assert detail["input_revision"] == 1
    assert detail["diagnosis"]["is_current"] is True


def test_omitted_external_consent_defaults_to_no_consent(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = client.post(
        f"/records/{record_id}/analyze",
        headers=auth_headers(token),
        data={"photo_roles": ["overview"], "location": "욕실 창가", "material": "실리콘"},
        files=[("photos", ("overview.png", PNG_1X1, "image/png"))],
    )
    assert response.status_code == 200, response.text
    assert "외부 분석 동의가 없어" in response.json()["photo_analysis"]["notice"]
