def test_cors_preflight_allows_local_expo_web(client):
    response = client.options(
        "/records",
        headers={
            "Origin": "http://localhost:8082",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8082"


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/records",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in response.headers
