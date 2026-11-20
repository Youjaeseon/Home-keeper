import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database():
    # These tests mock Supabase and never use the database.
    yield


@pytest.mark.parametrize(
    "status, payload, expected",
    [
        (200, {"access_token": "test-token", "token_type": "bearer", "expires_in": 3600, "refresh_token": "private"}, 200),
        (400, {"msg": "private upstream detail"}, 400),
        (429, {}, 429),
        (500, {}, 502),
        (200, {}, 502),
        (200, None, 502),
    ],
)
def test_scalar_login(monkeypatch, status, payload, expected):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")

    async def post(self, url, **kwargs):
        assert url == "http://127.0.0.1:54321/auth/v1/token"
        assert kwargs == {
            "params": {"grant_type": "password"},
            "headers": {"apikey": "public-test-key"},
            "json": {"email": "user@example.com", "password": "test-password"},
        }
        return httpx.Response(status, json=payload) if payload is not None else httpx.Response(status, text="not json")

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with TestClient(app) as client:
        result = client.post("/auth/token", data={"username": "user@example.com", "password": "test-password", "grant_type": "password"})
    assert result.status_code == expected
    assert result.headers["cache-control"] == "no-store"
    assert "private" not in result.text
    if expected == 200:
        assert result.json() == {"access_token": "test-token", "token_type": "bearer", "expires_in": 3600}
    else:
        assert "error_description" in result.json()


def test_scalar_login_network_failure(monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")

    async def post(self, *args, **kwargs):
        raise httpx.ConnectError("private connection detail")

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with TestClient(app) as client:
        result = client.post("/auth/token", data={"username": "user@example.com", "password": "test-password"})
    assert result.status_code == 502
    assert "private" not in result.text


def test_scalar_login_configuration_and_input(monkeypatch):
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    with TestClient(app) as client:
        assert client.post("/auth/token", data={"username": "user@example.com", "password": "test-password"}).status_code == 503
        assert client.post("/auth/token", data={"username": "user@example.com", "password": "test-password", "grant_type": "refresh_token"}).status_code == 400
        result = client.post("/auth/token", data={"password": "test-password"})
        assert result.status_code == 422
        assert "test-password" not in result.text


def test_scalar_offers_login_without_weakening_bearer_auth():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        assert schema["components"]["securitySchemes"]["SupabaseLogin"]["flows"]["password"]["tokenUrl"] == "/auth/token"
        assert "SupabaseLogin" in client.get("/docs").text
        for path in schema["paths"].values():
            for operation in path.values():
                if isinstance(operation, dict) and {"HTTPBearer": []} in operation.get("security", []):
                    assert {"SupabaseLogin": []} in operation["security"]
        assert "security" not in schema["paths"]["/health"]["get"]
        assert client.get("/records").status_code == 401
        assert client.get("/records", headers={"Authorization": "Bearer invalid"}).status_code == 401
