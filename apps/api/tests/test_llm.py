import dataclasses

import httpx
import pytest

from app import llm
from app.config import Settings


def _settings(**overrides):
    base = Settings(
        database_url="postgresql://localhost/test",
        supabase_url="http://127.0.0.1:54321",
        supabase_jwt_secret=None,
        supabase_jwt_audience="authenticated",
        supabase_jwt_issuer="http://127.0.0.1:54321/auth/v1",
        llm_api_key="test-key",
        llm_base_url="http://llm.local/v1",
        llm_model="test-model",
        llm_timeout_seconds=5,
    )
    return dataclasses.replace(base, **overrides)


class _Response:
    def __init__(self, status_code, payload=None, *, invalid_json=False):
        self.status_code = status_code
        self._payload = payload
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("not json")
        return self._payload


def test_generate_text_posts_chat_completion(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response(200, {"choices": [{"message": {"content": " 초안 본문 "}}]})

    monkeypatch.setattr("app.llm.get_settings", lambda: _settings())
    monkeypatch.setattr("app.llm.httpx.post", fake_post)

    assert llm.generate_text("요청 프롬프트") == "초안 본문"
    assert captured["url"] == "http://llm.local/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer test-key"}
    assert captured["timeout"] == 5
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["messages"][0] == {
        "role": "system",
        "content": llm.SYSTEM_PROMPT,
    }
    assert captured["json"]["messages"][1] == {
        "role": "user",
        "content": "요청 프롬프트",
    }


def test_generate_text_without_key_never_calls_the_provider(monkeypatch):
    monkeypatch.setattr("app.llm.get_settings", lambda: _settings(llm_api_key=None))

    def fail(*_args, **_kwargs):
        raise AssertionError("provider must not be called without a key")

    monkeypatch.setattr("app.llm.httpx.post", fail)
    with pytest.raises(llm.LlmUnavailable):
        llm.generate_text("x")


@pytest.mark.parametrize(
    "response",
    [
        _Response(401, {}),
        _Response(200, invalid_json=True),
        _Response(200, {"choices": []}),
        _Response(200, {"choices": [{"message": {"content": "   "}}]}),
        _Response(200, {"choices": [{"message": {"content": "x" * (llm.MAX_OUTPUT_CHARS + 1)}}]}),
        _Response(200, {"choices": [{"message": {"content": 42}}]}),
    ],
)
def test_unusable_responses_raise_llm_error(monkeypatch, response):
    monkeypatch.setattr("app.llm.get_settings", lambda: _settings())
    monkeypatch.setattr("app.llm.httpx.post", lambda *_args, **_kwargs: response)
    with pytest.raises(llm.LlmError):
        llm.generate_text("x")


def test_transport_timeout_and_failure_are_distinguished(monkeypatch):
    monkeypatch.setattr("app.llm.get_settings", lambda: _settings())

    def timeout(*_args, **_kwargs):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr("app.llm.httpx.post", timeout)
    with pytest.raises(llm.LlmTimeout):
        llm.generate_text("x")

    def broken(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("app.llm.httpx.post", broken)
    with pytest.raises(llm.LlmError):
        llm.generate_text("x")


def test_quota_errors_are_reported_separately(monkeypatch):
    monkeypatch.setattr("app.llm.get_settings", lambda: _settings())
    monkeypatch.setattr("app.llm.httpx.post", lambda *_args, **_kwargs: _Response(429, {}))
    with pytest.raises(llm.LlmQuotaExceeded):
        llm.generate_text("x")


def test_brief_high_demand_is_retried_once(monkeypatch):
    calls = []
    responses = [
        _Response(503, {}),
        _Response(200, {"choices": [{"message": {"content": "초안"}}]}),
    ]

    def fake_post(*_args, **_kwargs):
        calls.append(1)
        return responses[len(calls) - 1]

    monkeypatch.setattr("app.llm.get_settings", lambda: _settings())
    monkeypatch.setattr("app.llm.httpx.post", fake_post)
    monkeypatch.setattr("app.llm.time.sleep", lambda _seconds: None)
    assert llm.generate_text("x") == "초안"
    assert len(calls) == 2
