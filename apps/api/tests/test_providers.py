import contextlib
from uuid import uuid4

import psycopg
import pytest

from conftest import auth_headers


def _yongin_id(admin):
    return admin.execute("SELECT id FROM regions WHERE name = 'yongin'").fetchone()["id"]


def _work_type(admin, name):
    admin.execute(
        "INSERT INTO work_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
        (name,),
    )
    return admin.execute(
        "SELECT id FROM work_types WHERE name = %s", (name,)
    ).fetchone()["id"]


def _region(admin, name):
    admin.execute(
        "INSERT INTO regions (name, display_name) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
        (name, f"테스트 {name}"),
    )
    return admin.execute(
        "SELECT id FROM regions WHERE name = %s", (name,)
    ).fetchone()["id"]


def _provider(admin, name, *, regions=(), work_types=(), account_user_id=None):
    provider_id = uuid4()
    admin.execute(
        "INSERT INTO providers (id, name, phone, account_user_id) VALUES (%s, %s, %s, %s)",
        (provider_id, name, "031-000-0000", account_user_id),
    )
    for region_id in regions:
        admin.execute(
            "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
            (provider_id, region_id),
        )
    for work_type_id in work_types:
        admin.execute(
            "INSERT INTO provider_work_types (provider_id, work_type_id) VALUES (%s, %s)",
            (provider_id, work_type_id),
        )
    return provider_id


def test_provider_search_and_work_types_require_auth(client):
    assert client.get("/work-types").status_code == 401
    assert client.get(
        "/providers",
        params={"region_id": str(uuid4()), "work_type_id": str(uuid4())},
    ).status_code == 401


def test_work_types_list_seeded_options(client, user_factory, token_for):
    response = client.get("/work-types", headers=auth_headers(token_for(user_factory())))
    assert response.status_code == 200, response.text
    names = [item["name"] for item in response.json()]
    assert {"곰팡이 제거", "균열 보수", "벽지·도장 보수", "원인 점검"} <= set(names)
    assert names == sorted(names)
    for item in response.json():
        assert set(item) == {"work_type_id", "name"}


def test_provider_search_requires_known_region_and_work_type(
    client, admin, user_factory, token_for
):
    token = token_for(user_factory())
    headers = auth_headers(token)
    region_id = _yongin_id(admin)
    work_type_id = _work_type(admin, "검증 작업")

    assert client.get("/providers", headers=headers).status_code == 422
    assert client.get(
        "/providers", headers=headers, params={"region_id": str(region_id)}
    ).status_code == 422
    assert client.get(
        "/providers",
        headers=headers,
        params={"region_id": str(uuid4()), "work_type_id": str(work_type_id)},
    ).status_code == 422
    assert client.get(
        "/providers",
        headers=headers,
        params={"region_id": str(region_id), "work_type_id": str(uuid4())},
    ).status_code == 422


def test_provider_search_matches_both_region_and_work_type(
    client, admin, user_factory, token_for
):
    region_id = _yongin_id(admin)
    other_region_id = _region(admin, f"other-{uuid4().hex[:8]}")
    work_type_id = _work_type(admin, f"결로 보수 {uuid4().hex[:8]}")
    other_work_type_id = _work_type(admin, f"도배 {uuid4().hex[:8]}")
    account_user_id = user_factory()

    matching = _provider(
        admin,
        "용인 곰팡이 업체",
        regions=[region_id],
        work_types=[work_type_id],
        account_user_id=account_user_id,
    )
    region_only = _provider(admin, "지역만 맞는 업체", regions=[region_id])
    work_type_only = _provider(admin, "작업만 맞는 업체", work_types=[work_type_id])
    both_mismatch = _provider(
        admin, "둘 다 다른 업체", regions=[other_region_id], work_types=[work_type_id]
    )
    _provider(
        admin,
        "다른 작업 업체",
        regions=[region_id],
        work_types=[other_work_type_id],
    )

    response = client.get(
        "/providers",
        headers=auth_headers(token_for(user_factory())),
        params={"region_id": str(region_id), "work_type_id": str(work_type_id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_sample"] is False
    assert body["providers"] == [
        {
            "provider_id": str(matching),
            "name": "용인 곰팡이 업체",
            "phone": "031-000-0000",
            "chat_available": True,
            "is_sample": False,
        }
    ]
    returned = {item["provider_id"] for item in body["providers"]}
    assert str(region_only) not in returned
    assert str(work_type_only) not in returned
    assert str(both_mismatch) not in returned


def test_provider_search_returns_samples_only_when_nothing_matches(
    client, admin, user_factory, token_for
):
    region_id = _region(admin, f"empty-{uuid4().hex[:8]}")
    work_type_id = _work_type(admin, f"빈 작업 {uuid4().hex[:8]}")
    # A provider that matches another region only proves the sample fallback is not
    # triggered by unrelated rows.
    _provider(admin, "다른 지역 업체", regions=[_yongin_id(admin)], work_types=[work_type_id])

    response = client.get(
        "/providers",
        headers=auth_headers(token_for(user_factory())),
        params={"region_id": str(region_id), "work_type_id": str(work_type_id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_sample"] is True
    assert body["providers"]
    for item in body["providers"]:
        assert item["is_sample"] is True
        assert item["chat_available"] is False
        assert item["phone"] is None
        assert item["name"].startswith("시연용 샘플 업체")
    assert len({item["provider_id"] for item in body["providers"]}) == len(
        body["providers"]
    )

    other = client.get(
        "/providers",
        headers=auth_headers(token_for(user_factory())),
        params={"region_id": str(_yongin_id(admin)), "work_type_id": str(work_type_id)},
    ).json()
    assert other["is_sample"] is False
    assert [item["name"] for item in other["providers"]] == ["다른 지역 업체"]


def test_provider_search_database_error_is_not_hidden(
    client, user_factory, token_for, monkeypatch
):
    @contextlib.contextmanager
    def broken_read():
        raise psycopg.OperationalError("database is down")
        yield

    monkeypatch.setattr("app.providers.read_transaction", broken_read)
    response = client.get(
        "/providers",
        headers=auth_headers(token_for(user_factory())),
        params={"region_id": str(uuid4()), "work_type_id": str(uuid4())},
    )
    assert response.status_code == 500, response.text
    assert response.json() == {
        "code": "internal_error",
        "message": "요청을 처리하지 못했습니다.",
    }


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_provider_search_rejects_malformed_ids(
    client, admin, user_factory, token_for, bad_id
):
    response = client.get(
        "/providers",
        headers=auth_headers(token_for(user_factory())),
        params={"region_id": bad_id, "work_type_id": str(_yongin_id(admin))},
    )
    assert response.status_code == 422
