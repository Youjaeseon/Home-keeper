from uuid import uuid4

from conftest import auth_headers


def _yongin_id(admin):
    return admin.execute(
        "SELECT id FROM regions WHERE name = 'yongin'"
    ).fetchone()["id"]


def _profile_body(region_id, **overrides):
    body = {
        "nickname": "하자탐정",
        "region_id": str(region_id),
        "address": "용인시 수지구",
        "housing_type": "monthly_rent",
    }
    body.update(overrides)
    return body


def test_profile_requires_auth_and_is_scoped_to_the_token_user(client, admin, user_factory, token_for):
    assert client.get("/me/profile").status_code == 401
    assert client.put("/me/profile", json=_profile_body(_yongin_id(admin))).status_code == 401

    user_a = user_factory()
    user_b = user_factory()
    token_a = token_for(user_a)
    token_b = token_for(user_b)
    region_id = _yongin_id(admin)

    assert client.get("/me/profile", headers=auth_headers(token_a)).status_code == 404

    saved = client.put(
        "/me/profile",
        headers=auth_headers(token_a),
        json=_profile_body(region_id),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "nickname": "하자탐정",
        "role": "requester",
        "region_id": str(region_id),
        "address": "용인시 수지구",
        "housing_type": "monthly_rent",
        "provider_id": None,
    }

    fetched = client.get("/me/profile", headers=auth_headers(token_a))
    assert fetched.status_code == 200
    assert fetched.json() == saved.json()

    assert client.get("/me/profile", headers=auth_headers(token_b)).status_code == 404
    saved_b = client.put(
        "/me/profile",
        headers=auth_headers(token_b),
        json=_profile_body(region_id, nickname="다른 사용자"),
    )
    assert saved_b.status_code == 200, saved_b.text
    assert saved_b.json()["nickname"] == "다른 사용자"

    assert client.get(
        "/me/profile", headers=auth_headers(token_a)
    ).json() == saved.json()
    assert admin.execute(
        "SELECT count(*) AS count FROM profiles WHERE user_id IN (%s, %s)",
        (user_a, user_b),
    ).fetchone()["count"] == 2


def test_profile_validation_and_save_retry(client, admin, user_factory, token_for):
    user_id = user_factory()
    token = token_for(user_id)
    region_id = _yongin_id(admin)
    headers = auth_headers(token)

    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, role="provider"),
    ).status_code == 422
    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, user_id=str(user_id)),
    ).status_code == 422
    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, provider_id=str(uuid4())),
    ).status_code == 422
    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, housing_type="apartment"),
    ).status_code == 422
    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, nickname="   "),
    ).status_code == 422
    assert client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(uuid4()),
    ).status_code == 422
    assert admin.execute(
        "SELECT count(*) AS count FROM profiles WHERE user_id = %s", (user_id,)
    ).fetchone()["count"] == 0

    saved = client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(
            region_id,
            nickname="  하자탐정  ",
            address="   ",
        ),
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["nickname"] == "하자탐정"
    assert saved.json()["address"] is None
    assert saved.json()["role"] == "requester"

    retried = client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, nickname="  하자탐정  ", address="   "),
    )
    assert retried.status_code == 200, retried.text
    assert retried.json() == saved.json()
    assert admin.execute(
        "SELECT count(*) AS count FROM profiles WHERE user_id = %s", (user_id,)
    ).fetchone()["count"] == 1

    updated = client.put(
        "/me/profile",
        headers=headers,
        json=_profile_body(region_id, nickname="수정된 닉네임"),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["nickname"] == "수정된 닉네임"
    assert admin.execute(
        "SELECT count(*) AS count FROM profiles WHERE user_id = %s", (user_id,)
    ).fetchone()["count"] == 1


def test_provider_role_is_not_changed_by_requester_profile_upsert(
    client, admin, user_factory, token_for
):
    user_id = user_factory()
    region_id = _yongin_id(admin)
    admin.execute(
        """
        INSERT INTO profiles
            (user_id, nickname, role, region_id, housing_type)
        VALUES (%s, '업체 담당자', 'provider', %s, 'jeonse')
        """,
        (user_id, region_id),
    )
    provider_id = admin.execute(
        """
        INSERT INTO providers (name, phone, account_user_id)
        VALUES ('연결 업체', '031-000-0000', %s)
        RETURNING id
        """,
        (user_id,),
    ).fetchone()["id"]
    token = token_for(user_id)

    fetched = client.get("/me/profile", headers=auth_headers(token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["role"] == "provider"
    assert fetched.json()["provider_id"] == str(provider_id)

    response = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json=_profile_body(region_id, nickname="업체 수정"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "provider"
    assert response.json()["nickname"] == "업체 수정"
    assert response.json()["provider_id"] == str(provider_id)
    assert admin.execute(
        "SELECT role FROM profiles WHERE user_id = %s", (user_id,)
    ).fetchone()["role"] == "provider"


def test_regions_are_public_and_include_demo_region(client, admin):
    # The signup screen loads regions before login.
    response = client.get("/regions")
    assert response.status_code == 200, response.text
    regions = response.json()
    assert regions
    yongin = next(region for region in regions if region["name"] == "yongin")
    gyeonggi = next(region for region in regions if region["name"] == "gyeonggi")
    assert gyeonggi["parent_id"] is None
    assert yongin == {
        "region_id": str(_yongin_id(admin)),
        "name": "yongin",
        "display_name": "경기도 용인시",
        "parent_id": gyeonggi["region_id"],
    }


def test_user_can_register_as_provider(client, admin, user_factory, token_for):
    user_id = user_factory()
    token = token_for(user_id)
    region_id = _yongin_id(admin)

    response = client.post(
        "/me/provider",
        headers=auth_headers(token),
        json={"name": "용인 하자케어", "phone": "031-000-0000", "description": "곰팡이 제거", "region_id": str(region_id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "provider"
    assert body["nickname"] == "용인 하자케어"
    assert body["provider_id"]

    provider = admin.execute(
        "SELECT name, phone, account_user_id FROM providers WHERE id = %s", (body["provider_id"],)
    ).fetchone()
    assert provider["account_user_id"] == user_id
    assert admin.execute(
        "SELECT 1 FROM provider_regions WHERE provider_id = %s AND region_id = %s",
        (body["provider_id"], region_id),
    ).fetchone()

    again = client.post(
        "/me/provider",
        headers=auth_headers(token),
        json={"name": "용인 하자케어2", "phone": "031-000-0001", "region_id": str(region_id)},
    )
    assert again.status_code == 200, again.text
    assert again.json()["provider_id"] == body["provider_id"]

    profile = client.get("/me/profile", headers=auth_headers(token)).json()
    assert profile["role"] == "provider"
    assert profile["provider_id"] == body["provider_id"]
