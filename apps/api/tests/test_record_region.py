from uuid import uuid4

from conftest import PNG_1X1, auth_headers


def _region_id(admin, name: str):
    return admin.execute("SELECT id FROM regions WHERE name = %s", (name,)).fetchone()["id"]


def _create_region(admin, display_name: str):
    return admin.execute(
        "INSERT INTO regions (name, display_name) VALUES (%s, %s) RETURNING id",
        (f"region-{uuid4().hex[:8]}", display_name),
    ).fetchone()["id"]


def _profile(client, token, region_id):
    response = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json={
            "nickname": "지역 사용자",
            "region_id": str(region_id),
            "address": None,
            "housing_type": "monthly_rent",
        },
    )
    assert response.status_code == 200, response.text


def _analyze(client, token, record_id, region_id=None):
    data = {
        "photo_roles": "overview",
        "external_analysis_consent": "false",
        "location": "안방 창틀",
        "material": "실리콘",
        "symptoms": "검은 얼룩",
    }
    if region_id is not None:
        data["region_id"] = str(region_id)
    return client.post(
        f"/records/{record_id}/analyze",
        headers=auth_headers(token),
        data=data,
        files=[("photos", ("photo.png", PNG_1X1, "image/png"))],
    )


def _detail(client, token, record_id):
    return client.get(
        f"/records/{record_id}", headers=auth_headers(token)
    ).json()


def test_analyze_snapshots_profile_region_and_keeps_it_on_reanalyze(
    client, admin, user_factory, token_for, record_factory
):
    yongin = _region_id(admin, "yongin")
    user_id = user_factory()
    token = token_for(user_id)
    _profile(client, token, yongin)
    record_id = record_factory(user_id)["record_id"]

    first = _analyze(client, token, record_id)
    assert first.status_code == 200, first.text
    assert first.json()["region_id"] == str(yongin)
    assert first.json()["input_revision"] == 1

    detail = _detail(client, token, record_id)
    assert detail["region_id"] == str(yongin)
    assert detail["region_name"] == "경기도 용인시"

    listed = client.get("/records", headers=auth_headers(token)).json()
    assert listed[0]["region_id"] == str(yongin)
    assert listed[0]["region_name"] == "경기도 용인시"

    second = _analyze(client, token, record_id)
    assert second.status_code == 200, second.text
    assert second.json()["region_id"] == str(yongin)
    assert second.json()["input_revision"] == 1
    assert second.json()["diagnosis_generation"] == 2


def test_analyze_without_profile_keeps_region_null(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = _analyze(client, token, record_id)
    assert response.status_code == 200, response.text
    assert response.json()["region_id"] is None
    detail = _detail(client, token, record_id)
    assert detail["region_id"] is None
    assert detail["region_name"] is None


def test_analyze_explicit_region_overrides_and_bumps_revision(
    client, admin, user_factory, token_for, record_factory
):
    yongin = _region_id(admin, "yongin")
    other = _create_region(admin, "테스트 지역")
    user_id = user_factory()
    token = token_for(user_id)
    _profile(client, token, yongin)
    record_id = record_factory(user_id)["record_id"]

    first = _analyze(client, token, record_id)
    assert first.json()["region_id"] == str(yongin)
    changed = _analyze(client, token, record_id, other)
    assert changed.status_code == 200, changed.text
    assert changed.json()["region_id"] == str(other)
    assert changed.json()["input_revision"] == 2
    assert _detail(client, token, record_id)["region_name"] == "테스트 지역"

    invalid = _analyze(client, token, record_id, uuid4())
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"
    current = _detail(client, token, record_id)
    assert current["region_id"] == str(other)
    assert current["input_revision"] == 2


def test_patch_region_validates_clears_and_bumps_revision(
    client, admin, user_factory, token_for, record_factory
):
    yongin = _region_id(admin, "yongin")
    other = _create_region(admin, "테스트 지역")
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    set_region = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"region_id": str(yongin)},
    )
    assert set_region.status_code == 200, set_region.text
    assert set_region.json()["region_id"] == str(yongin)
    assert set_region.json()["input_revision"] == 1

    same = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"region_id": str(yongin)},
    )
    assert same.status_code == 200
    assert same.json()["input_revision"] == 1

    changed = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"region_id": str(other)},
    )
    assert changed.status_code == 200
    assert changed.json()["region_id"] == str(other)
    assert changed.json()["input_revision"] == 2

    invalid = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"region_id": str(uuid4())},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"
    assert _detail(client, token, record_id)["region_id"] == str(other)

    cleared = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"region_id": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["region_id"] is None
    assert cleared.json()["input_revision"] == 3
    assert _detail(client, token, record_id)["region_name"] is None


def test_patch_requires_at_least_one_region_or_input_field(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    response = client.patch(
        f"/records/{record_id}", headers=auth_headers(token), json={}
    )
    assert response.status_code == 422


def test_analyze_accepts_explicit_region_without_profile(
    client, admin, user_factory, token_for, record_factory
):
    yongin = _region_id(admin, "yongin")
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = _analyze(client, token, record_id, yongin)
    assert response.status_code == 200, response.text
    assert response.json()["region_id"] == str(yongin)
    detail = _detail(client, token, record_id)
    assert detail["region_id"] == str(yongin)
    assert detail["region_name"] == "경기도 용인시"
