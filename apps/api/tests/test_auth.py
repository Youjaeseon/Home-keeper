from datetime import datetime, timedelta, timezone

import jwt
import pytest

from conftest import auth_headers


def test_missing_and_malformed_tokens_are_rejected(client):
    for headers in ({}, {"Authorization": "Bearer not-a-jwt"}):
        response = client.post("/records", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"


def test_unsigned_token_is_rejected(client, user_factory):
    user_id = user_factory()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "iss": "http://127.0.0.1:54321/auth/v1",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        key=None,
        algorithm="none",
    )
    response = client.post("/records", headers=auth_headers(token))
    assert response.status_code == 401


@pytest.mark.parametrize("expires_in", [-31, -60])
def test_expired_token_is_rejected(client, user_factory, token_for, expires_in):
    user_id = user_factory()
    response = client.post(
        "/records", headers=auth_headers(token_for(user_id, expires_in=expires_in))
    )
    assert response.status_code == 401


@pytest.mark.parametrize("issued_in, status", [(4, 200), (29, 200), (60, 401)])
def test_token_issue_time_allows_small_clock_skew(
    client, user_factory, token_for, issued_in, status
):
    user_id = user_factory()
    # /regions is public, so use an authenticated read endpoint.
    response = client.get(
        "/work-types", headers=auth_headers(token_for(user_id, issued_in=issued_in))
    )
    assert response.status_code == status


def test_wrong_signature_is_rejected(client, user_factory, token_for):
    user_id = user_factory()
    response = client.post(
        "/records",
        headers=auth_headers(token_for(user_id, secret="wrong-secret-long-enough-for-hs256-signing")),
    )
    assert response.status_code == 401


def test_wrong_audience_or_issuer_is_rejected(client, user_factory, token_for):
    user_id = user_factory()
    wrong_audience = token_for(user_id, audience="other")
    wrong_issuer = token_for(user_id, issuer="http://evil.example/auth/v1")
    for token in (wrong_audience, wrong_issuer):
        response = client.post("/records", headers=auth_headers(token))
        assert response.status_code == 401


def test_non_uuid_subject_is_rejected(client, user_factory, token_for):
    response = client.post(
        "/records", headers=auth_headers(token_for("not-a-uuid"))
    )
    assert response.status_code == 401


def test_valid_token_creates_record_for_subject(client, user_factory, token_for):
    user_id = user_factory()
    response = client.post("/records", headers=auth_headers(token_for(user_id)))
    assert response.status_code == 201
    body = response.json()
    assert body["input_revision"] == 0

    detail = client.get(
        f"/records/{body['record_id']}", headers=auth_headers(token_for(user_id))
    )
    assert detail.status_code == 200


def test_auth_boundary_can_be_overridden_in_tests(client, user_factory):
    from app.auth import get_current_user
    from app.main import app

    user_id = user_factory()
    app.dependency_overrides[get_current_user] = lambda: user_id
    try:
        response = client.post("/records")
        assert response.status_code == 201
    finally:
        app.dependency_overrides.pop(get_current_user, None)
