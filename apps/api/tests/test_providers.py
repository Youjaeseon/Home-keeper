import contextlib
from pathlib import Path
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


def _provider(
    admin,
    name,
    *,
    regions=(),
    work_types=(),
    account_user_id=None,
    rating=0.0,
    review_count=0,
    description=None,
    address=None,
    business_hours=None,
    career_years=None,
    phone="031-000-0000",
):
    provider_id = uuid4()
    admin.execute(
        """
        INSERT INTO providers
            (id, name, phone, rating, review_count, description, address,
             business_hours, career_years, account_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            provider_id,
            name,
            phone,
            rating,
            review_count,
            description,
            address,
            business_hours,
            career_years,
            account_user_id,
        ),
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


def work_type_id_name(admin, work_type_id):
    return admin.execute(
        "SELECT name FROM work_types WHERE id = %s", (work_type_id,)
    ).fetchone()["name"]


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
    ).status_code == 200
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
            "rating": 0.0,
            "review_count": 0,
            "description": None,
            "specialty_work_types": [
                {"work_type_id": str(work_type_id), "name": work_type_id_name(admin, work_type_id)}
            ],
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
        assert item["rating"] == 0.0
        assert item["review_count"] == 0
        assert item["description"] is None
        assert item["specialty_work_types"] == []
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


def test_provider_search_sorts_by_rating_reviews_and_name(
    client, admin, user_factory, token_for
):
    region_id = _region(admin, f"rank-{uuid4().hex[:8]}")
    work_a = _work_type(admin, f"정렬 작업 A {uuid4().hex[:8]}")
    work_b = _work_type(admin, f"정렬 작업 B {uuid4().hex[:8]}")
    alpha = _provider(
        admin, "Alpha", regions=[region_id], work_types=[work_b],
        rating=4.0, review_count=99,
    )
    zulu = _provider(
        admin, "Zulu", regions=[region_id], work_types=[work_a],
        rating=4.5, review_count=1,
    )
    beta = _provider(
        admin, "Beta", regions=[region_id], work_types=[work_a, work_b],
        rating=4.8, review_count=5,
    )
    charlie = _provider(
        admin, "Charlie", regions=[region_id], work_types=[work_b],
        rating=4.8, review_count=5,
    )
    delta = _provider(
        admin, "Delta", regions=[region_id], work_types=[work_a],
        rating=4.8, review_count=10,
    )

    headers = auth_headers(token_for(user_factory()))
    all_body = client.get(
        "/providers", headers=headers, params={"region_id": str(region_id)}
    ).json()
    assert [item["provider_id"] for item in all_body["providers"]] == [
        str(delta), str(beta), str(charlie), str(zulu), str(alpha)
    ]
    assert all_body["providers"][0]["rating"] == 4.8
    assert all_body["providers"][0]["review_count"] == 10
    beta_item = next(item for item in all_body["providers"] if item["provider_id"] == str(beta))
    assert [item["name"] for item in beta_item["specialty_work_types"]] == sorted(
        [work_type_id_name(admin, work_a), work_type_id_name(admin, work_b)]
    )

    filtered = client.get(
        "/providers",
        headers=headers,
        params={"region_id": str(region_id), "work_type_id": str(work_a)},
    ).json()
    assert [item["provider_id"] for item in filtered["providers"]] == [
        str(delta), str(beta), str(zulu)
    ]
    assert all(
        any(item["work_type_id"] == str(work_a) for item in provider["specialty_work_types"])
        for provider in filtered["providers"]
    )


def test_provider_detail_returns_regions_work_types_and_profile_fields(
    client, admin, user_factory, token_for
):
    yongin = _yongin_id(admin)
    other = _region(admin, f"detail-{uuid4().hex[:8]}")
    work_a = _work_type(admin, f"상세 작업 A {uuid4().hex[:8]}")
    work_b = _work_type(admin, f"상세 작업 B {uuid4().hex[:8]}")
    provider_id = _provider(
        admin,
        "상세 업체",
        regions=[other, yongin],
        work_types=[work_b, work_a],
        rating=4.7,
        review_count=12,
        description="결로와 곰팡이를 함께 점검합니다.",
        address="경기도 용인시 수지구",
        business_hours="평일 09:00~18:00",
        career_years=8,
        phone="031-123-4567",
    )

    response = client.get(
        f"/providers/{provider_id}",
        headers=auth_headers(token_for(user_factory())),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_id"] == str(provider_id)
    assert body["name"] == "상세 업체"
    assert body["phone"] == "031-123-4567"
    assert body["rating"] == 4.7
    assert body["review_count"] == 12
    assert body["description"] == "결로와 곰팡이를 함께 점검합니다."
    assert body["address"] == "경기도 용인시 수지구"
    assert body["business_hours"] == "평일 09:00~18:00"
    assert body["career_years"] == 8
    assert body["chat_available"] is False
    assert body["is_sample"] is False
    assert [region["region_id"] for region in body["regions"]] == sorted(
        [str(yongin), str(other)],
        key=lambda region_id: (
            admin.execute(
                "SELECT display_name FROM regions WHERE id = %s", (region_id,)
            ).fetchone()["display_name"],
            region_id,
        ),
    )
    assert {item["work_type_id"] for item in body["work_types"]} == {
        str(work_a), str(work_b)
    }


def test_provider_detail_requires_auth_and_rejects_unknown_ids(
    client, user_factory, token_for
):
    provider_id = uuid4()
    assert client.get(f"/providers/{provider_id}").status_code == 401

    token = token_for(user_factory())
    for missing in (
        provider_id,
        "00000000-0000-4000-8000-000000000001",
    ):
        response = client.get(
            f"/providers/{missing}", headers=auth_headers(token)
        )
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    invalid = client.get("/providers/not-a-uuid", headers=auth_headers(token))
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"


def test_provider_rating_and_review_check_constraints(admin):
    for rating in (-0.1, 5.1):
        with pytest.raises(psycopg.errors.CheckViolation):
            admin.execute(
                "INSERT INTO providers (name, phone, rating) VALUES (%s, %s, %s)",
                (f"평점 오류 {rating}", "031-000-0000", rating),
            )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            "INSERT INTO providers (name, phone, review_count) VALUES (%s, %s, -1)",
            ("리뷰 오류", "031-000-0000"),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            "INSERT INTO providers (name, phone, career_years) VALUES (%s, %s, -1)",
            ("경력 오류", "031-000-0000"),
        )


def test_yongin_provider_seed_template_is_idempotent(admin):
    seed_file = Path(__file__).resolve().parents[1] / "migrations/014_yongin_provider_seed.sql"
    before = admin.execute("SELECT count(*) AS count FROM providers").fetchone()["count"]
    admin.execute(seed_file.read_text())
    first = admin.execute("SELECT count(*) AS count FROM providers").fetchone()["count"]
    admin.execute(seed_file.read_text())
    second = admin.execute("SELECT count(*) AS count FROM providers").fetchone()["count"]
    assert first == second == before
