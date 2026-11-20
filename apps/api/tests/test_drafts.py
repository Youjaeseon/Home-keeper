import asyncio
import dataclasses
import threading

import httpx

from app import llm
from app.config import get_settings
from app.main import app
from conftest import PNG_1X1, auth_headers


def _fake_llm(monkeypatch):
    calls = []

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return f"초안 {len(calls)}"

    monkeypatch.setattr("app.llm.generate_text", generate)
    return calls


def _draft(client, token, record_id, kind="landlord", *, regenerate=False):
    return client.post(
        f"/records/{record_id}/drafts/{kind}",
        headers=auth_headers(token),
        params={"regenerate": "true"} if regenerate else None,
    )


def _template(client, token, record_id, kind="landlord"):
    return client.get(
        f"/records/{record_id}/drafts/{kind}/template",
        headers=auth_headers(token),
    )


def test_draft_requires_owned_record_and_supported_kind(
    client, user_factory, token_for, record_factory, monkeypatch
):
    _fake_llm(monkeypatch)
    owner = user_factory()
    token = token_for(owner)
    other_token = token_for(user_factory())
    record_id = record_factory(owner)["record_id"]

    assert client.post(f"/records/{record_id}/drafts/landlord").status_code == 401
    assert client.get(f"/records/{record_id}/drafts/landlord/template").status_code == 401

    for kind in ("landlord", "provider"):
        assert _draft(client, other_token, record_id, kind).status_code == 404
        assert _template(client, other_token, record_id, kind).status_code == 404

    assert _draft(client, token, record_id, "neighbor").status_code == 422
    assert _template(client, token, record_id, "neighbor").status_code == 422


def test_draft_without_diagnosis_refuses_generation_but_template_works(
    client, user_factory, token_for, record_factory, monkeypatch
):
    calls = _fake_llm(monkeypatch)
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"location": "안방 창틀 아래", "material": "실리콘", "symptoms": "곰팡이 의심"},
    )

    response = _draft(client, token, record_id)
    assert response.status_code == 409, response.text
    assert response.json() == {
        "code": "diagnosis_required",
        "message": "진단 결과가 없어 요청문을 생성할 수 없습니다. 먼저 분석을 완료하거나 기본 양식을 사용해 주세요.",
        "input_revision": 1,
    }
    assert calls == []

    template = _template(client, token, record_id)
    assert template.status_code == 200, template.text
    body = template.json()
    assert body["kind"] == "landlord"
    assert body["input_revision"] == 1
    assert body["diagnosis_generation"] is None
    assert "안방 창틀 아래" in body["text"]
    assert "실리콘" in body["text"]
    assert "곰팡이 의심" in body["text"]
    assert "아직 진단 결과가 없습니다" in body["text"]
    assert calls == []

    provider_template = _template(client, token, record_id, "provider").json()
    assert "견적" in provider_template["text"]


def test_draft_reuse_explicit_regenerate_and_version_changes(
    client, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    calls = _fake_llm(monkeypatch)
    user_id = user_factory()
    token = token_for(user_id)
    record_id = analyzed_record_factory(user_id)

    first = _draft(client, token, record_id)
    assert first.status_code == 200, first.text
    assert first.json() == {
        "kind": "landlord",
        "text": "초안 1",
        "input_revision": 1,
        "diagnosis_generation": 1,
    }
    assert len(calls) == 1

    reused = _draft(client, token, record_id)
    assert reused.json() == first.json()
    assert len(calls) == 1

    regenerated = _draft(client, token, record_id, regenerate=True)
    assert regenerated.json()["text"] == "초안 2"
    assert len(calls) == 2

    patched = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"symptoms": "닦아도 다시 생기는 검은 얼룩"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["input_revision"] == 2

    after_input = _draft(client, token, record_id)
    assert after_input.json()["text"] == "초안 3"
    assert after_input.json()["input_revision"] == 2
    assert after_input.json()["diagnosis_generation"] == 1

    detail = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()
    assert detail["drafts"]["landlord"] == {
        "text": "초안 3",
        "input_revision": 2,
        "diagnosis_generation": 1,
        "is_current": True,
    }

    # Same input re-analysis only bumps the diagnosis generation.
    detail_before = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()
    assert detail_before["input_revision"] == 2
    analyzed = client.post(
        f"/records/{record_id}/analyze",
        headers=auth_headers(token),
        data={
            "photo_roles": ["overview"],
            "external_analysis_consent": "false",
            "location": "안방 창틀 아래",
            "material": "실리콘",
            "symptoms": "닦아도 다시 생기는 검은 얼룩",
        },
        files=[("photos", ("overview.png", PNG_1X1, "image/png"))],
    )
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["input_revision"] == 2
    assert analyzed.json()["diagnosis_generation"] == 2

    after_generation = _draft(client, token, record_id)
    assert after_generation.json()["text"] == "초안 4"
    assert after_generation.json()["input_revision"] == 2
    assert after_generation.json()["diagnosis_generation"] == 2

    stale = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()
    assert stale["drafts"]["landlord"]["is_current"] is True
    assert stale["drafts"]["landlord"]["text"] == "초안 4"


def _run_with_concurrent_change(admin, token, record_id, started, release, sql, params):
    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            pending = asyncio.create_task(
                client.post(
                    f"/records/{record_id}/drafts/landlord",
                    headers=auth_headers(token),
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 10)
                admin.execute(sql, params)
            finally:
                release.set()
            return await pending

    return asyncio.run(scenario())


def _blocking_llm(monkeypatch, started):
    release = threading.Event()

    def generate(_prompt: str) -> str:
        started.set()
        assert release.wait(10)
        return "늦게 도착한 초안"

    monkeypatch.setattr("app.llm.generate_text", generate)
    return release


def test_draft_is_not_saved_when_input_changes_during_generation(
    client, admin, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = analyzed_record_factory(user_id)

    started = threading.Event()
    release = _blocking_llm(monkeypatch, started)
    response = _run_with_concurrent_change(
        admin,
        token,
        record_id,
        started,
        release,
        "UPDATE records SET symptoms = '바뀐 증상', input_revision = input_revision + 1 WHERE id = %s",
        (record_id,),
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "revision_conflict"
    assert response.json()["input_revision"] == 2
    draft = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()["drafts"]
    assert draft["landlord"] is None


def test_draft_is_not_saved_when_diagnosis_changes_during_generation(
    client, admin, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = analyzed_record_factory(user_id)

    started = threading.Event()
    release = _blocking_llm(monkeypatch, started)
    response = _run_with_concurrent_change(
        admin,
        token,
        record_id,
        started,
        release,
        "UPDATE records SET diagnosis_generation = diagnosis_generation + 1 WHERE id = %s",
        (record_id,),
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "diagnosis_conflict"
    assert response.json()["input_revision"] == 1
    draft = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()["drafts"]
    assert draft["landlord"] is None


def test_llm_failures_keep_the_previous_draft_and_template_stays_usable(
    client, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    calls = _fake_llm(monkeypatch)
    user_id = user_factory()
    token = token_for(user_id)
    record_id = analyzed_record_factory(user_id)

    assert _draft(client, token, record_id).json()["text"] == "초안 1"
    assert len(calls) == 1
    client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"symptoms": "새로 번진 얼룩"},
    )

    def raiser(exc):
        def generate(_prompt: str) -> str:
            raise exc

        return generate

    for exc, status, code in (
        (llm.LlmError(), 502, "llm_error"),
        (llm.LlmTimeout(), 504, "llm_timeout"),
        (llm.LlmUnavailable(), 503, "llm_unavailable"),
    ):
        monkeypatch.setattr("app.llm.generate_text", raiser(exc))
        response = _draft(client, token, record_id)
        assert response.status_code == status, response.text
        assert response.json()["code"] == code
        assert "샘플" not in response.text

        draft = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()[
            "drafts"
        ]["landlord"]
        assert draft["text"] == "초안 1"
        assert draft["is_current"] is False

        template = _template(client, token, record_id)
        assert template.status_code == 200
        assert "새로 번진 얼룩" in template.json()["text"]


def test_unconfigured_model_key_returns_error_without_sample_text(
    client, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = analyzed_record_factory(user_id)
    settings = dataclasses.replace(get_settings(), llm_api_key=None)
    monkeypatch.setattr("app.llm.get_settings", lambda: settings)

    response = _draft(client, token, record_id)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "llm_unavailable"
    assert "샘플" not in response.text
    assert client.get(f"/records/{record_id}", headers=auth_headers(token)).json()[
        "drafts"
    ]["landlord"] is None

    template = _template(client, token, record_id)
    assert template.status_code == 200
    assert template.json()["diagnosis_generation"] == 1


def test_model_prompt_excludes_profile_data_and_redacts_contact_details(
    client, admin, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    calls = _fake_llm(monkeypatch)
    user_id = user_factory()
    token = token_for(user_id)
    region_id = admin.execute(
        "SELECT id FROM regions WHERE name = 'yongin'"
    ).fetchone()["id"]
    profile = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json={
            "nickname": "비공개닉네임",
            "region_id": str(region_id),
            "address": "용인시 수지구 비공개로 123",
            "housing_type": "monthly_rent",
        },
    )
    assert profile.status_code == 200, profile.text

    record_id = analyzed_record_factory(
        user_id,
        symptoms="창틀 곰팡이. 연락처 010-1234-5678, 메일 mold.test@example.com",
    )

    response = _draft(client, token, record_id, "provider")
    assert response.status_code == 200, response.text
    prompt = calls[0]
    assert "안방 창틀 아래" in prompt
    assert "실리콘" in prompt
    assert "[개인정보 제거]" in prompt
    for secret in (
        "비공개닉네임",
        "용인시 수지구 비공개로 123",
        "010-1234-5678",
        "mold.test@example.com",
        "monthly_rent",
    ):
        assert secret not in prompt
