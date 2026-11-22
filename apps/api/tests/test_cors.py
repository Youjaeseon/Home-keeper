from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def database():
    # CORS and authentication rejection do not access the database.
    yield


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def cors_client(monkeypatch):
    def create(origins):
        if origins is None:
            monkeypatch.delenv("CORS_ORIGINS", raising=False)
        else:
            monkeypatch.setenv("CORS_ORIGINS", origins)
        # Load the real app without replacing the shared app used by other tests.
        app = run_path(str(Path(__file__).parents[1] / "app" / "main.py"))["app"]
        return TestClient(app)

    return create


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ()),
        ("", ()),
        (" ,  , ", ()),
        ("http://localhost:8081", ("http://localhost:8081",)),
        (
            " http://localhost:8081, , http://127.0.0.1:8081, ",
            ("http://localhost:8081", "http://127.0.0.1:8081"),
        ),
    ],
)
def test_cors_origins_environment(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", raw)
    assert get_settings().cors_origins == expected


@pytest.mark.parametrize("origins", [None, "", " , , "])
def test_cors_disabled_without_origins(cors_client, origins):
    with cors_client(origins) as client:
        headers = {"Origin": "http://localhost:8081"}
        response = client.get("/health", headers=headers)
        preflight = client.options(
            "/records",
            headers={**headers, "Access-Control-Request-Method": "POST"},
        )
    assert response.status_code == 200
    assert preflight.status_code == 405
    for result in (response, preflight):
        assert not any(name.startswith("access-control-") for name in result.headers)


@pytest.mark.parametrize("origin", ["http://localhost:8081", "http://127.0.0.1:8081"])
def test_allowed_origin_gets_cors_headers(cors_client, origin):
    with cors_client(" http://localhost:8081, , http://127.0.0.1:8081, ") as client:
        response = client.get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["access-control-allow-origin"] == origin
    assert "origin" in response.headers["vary"].lower()
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_preflight_allows_methods_and_authorization_header(cors_client, method):
    origin = "http://localhost:8081"
    with cors_client(origin) as client:
        response = client.options(
            "/records",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert method in response.headers["access-control-allow-methods"].split(", ")
    assert {"authorization", "content-type"} <= set(
        response.headers["access-control-allow-headers"].lower().split(",")
    )
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    "origin",
    ["https://untrusted.example", "http://localhost:8082", "http://localhost:8081.evil.example"],
)
def test_unlisted_origin_is_not_allowed(cors_client, origin):
    with cors_client("http://localhost:8081") as client:
        response = client.get("/health", headers={"Origin": origin})
        preflight = client.options(
            "/records",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
    # Simple requests still reach the API; browsers enforce the missing CORS header.
    assert response.status_code == 200
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-origin" not in preflight.headers


def test_request_without_origin_works_without_cors_headers(cors_client):
    with cors_client("http://localhost:8081") as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("authorization", [None, "Bearer invalid"])
def test_cors_keeps_authentication_errors_readable(cors_client, authorization):
    origin = "http://localhost:8081"
    headers = {"Origin": origin}
    if authorization:
        headers["Authorization"] = authorization
    with cors_client(origin) as client:
        response = client.get("/records", headers=headers)
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == origin
