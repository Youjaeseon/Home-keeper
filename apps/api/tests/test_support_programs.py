from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from conftest import auth_headers

SEED_FILE = Path(__file__).resolve().parents[1] / "migrations/009_support_program_seed.sql"


def _region_id(admin, name: str):
    return admin.execute("SELECT id FROM regions WHERE name = %s", (name,)).fetchone()["id"]


def _create_region(admin, name: str, display_name: str, parent_id=None):
    return admin.execute(
        """
        INSERT INTO regions (name, display_name, parent_id)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (name, display_name, parent_id),
    ).fetchone()["id"]


def _profile(client, token, region_id, housing_type="monthly_rent"):
    response = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json={
            "nickname": "소식지 사용자",
            "region_id": str(region_id),
            "address": None,
            "housing_type": housing_type,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _insert_program(
    admin,
    *,
    region_id,
    title,
    deadline_kind,
    deadline_date=None,
    deadline_text=None,
    housing_types=(),
    region_scope="local",
    external_id=None,
    source="gov24_api",
    order_title=None,
    organization_name="테스트 기관",
):
    return admin.execute(
        """
        INSERT INTO support_programs (
            external_id, source, title, summary, organization_name,
            region_scope, region_id, target_housing_types, support_target,
            support_content, selection_criteria, apply_method, deadline_text,
            deadline_date, deadline_kind, detail_url, source_attribution
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s, %s,
            'https://example.com/support-program', '검증용 출처'
        )
        RETURNING id
        """,
        (
            external_id or f"test:{uuid4()}",
            source,
            order_title or title,
            f"{title} 요약",
            organization_name,
            region_scope,
            region_id,
            list(housing_types),
            "테스트 지원 대상",
            "테스트 지원 내용",
            deadline_text,
            deadline_date,
            deadline_kind,
        ),
    ).fetchone()["id"]


def _seed_ids(admin):
    return {
        row["external_id"]: str(row["id"])
        for row in admin.execute(
            "SELECT id, external_id FROM support_programs WHERE external_id LIKE 'seed:%'"
        ).fetchall()
    }


@pytest.fixture
def empty_support_programs(admin):
    admin.execute(
        "CREATE TEMP TABLE support_programs_backup AS SELECT * FROM support_programs"
    )
    admin.execute("DELETE FROM support_programs")
    try:
        yield
    finally:
        admin.execute(
            "INSERT INTO support_programs SELECT * FROM support_programs_backup"
        )
        admin.execute("DROP TABLE support_programs_backup")


def test_support_program_auth_profile_and_detail_errors(
    client, admin, user_factory, token_for
):
    assert client.get("/support-programs").status_code == 401
    assert client.get(f"/support-programs/{uuid4()}").status_code == 401

    token = token_for(user_factory())
    missing_profile = client.get("/support-programs", headers=auth_headers(token))
    assert missing_profile.status_code == 404
    assert missing_profile.json()["code"] == "not_found"

    national_id = _seed_ids(admin)["seed:gov24-youth-monthly-rent-2026"]
    detail = client.get(
        f"/support-programs/{national_id}", headers=auth_headers(token)
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == national_id
    assert body["source"] == "seed"
    assert body["deadline_kind"] == "fixed"
    assert body["deadline_date"] == "2026-05-29"
    assert body["detail_url"].startswith("https://")
    assert body["source_checked_at"]
    assert body["support_target"]
    assert body["support_content"]
    assert body["source_attribution"]

    missing = client.get(
        f"/support-programs/{uuid4()}", headers=auth_headers(token)
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"

    invalid = client.get("/support-programs/not-a-uuid", headers=auth_headers(token))
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"

    invalid_status = client.get(
        "/support-programs?status=closed", headers=auth_headers(token)
    )
    assert invalid_status.status_code == 422
    assert invalid_status.json()["code"] == "invalid_request"


def test_support_programs_list_local_parent_national_and_excludes_other_regions(
    client, admin, user_factory, token_for
):
    user_id = user_factory()
    token = token_for(user_id)
    _profile(client, token, _region_id(admin, "yongin"))

    other_region = _create_region(
        admin, f"other-{uuid4().hex[:8]}", f"다른지역-{uuid4().hex[:6]}"
    )
    other_program = str(
        _insert_program(
            admin,
            region_id=other_region,
            title="다른 지역 공고",
            deadline_kind="unknown",
        )
    )

    response = client.get("/support-programs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    ids = {item["id"] for item in items}
    seed_ids = _seed_ids(admin)

    assert seed_ids["seed:gov24-youth-monthly-rent-2026"] in ids
    assert seed_ids["seed:gyeonggi-independent-youth-housing-2026"] in ids
    assert seed_ids["seed:yongin-youth-brokerage-fee-2026"] in ids
    assert seed_ids["seed:yongin-youth-monthly-rent-2026"] in ids
    assert other_program not in ids

    by_id = {item["id"]: item for item in items}
    assert (
        by_id[seed_ids["seed:gyeonggi-independent-youth-housing-2026"]]["region_name"]
        == "경기도"
    )
    assert (
        by_id[seed_ids["seed:yongin-youth-brokerage-fee-2026"]]["region_name"]
        == "경기도 용인시"
    )
    assert (
        by_id[seed_ids["seed:gov24-youth-monthly-rent-2026"]]["region_name"]
        == "전국"
    )

    duplicate_api_id = str(
        _insert_program(
            admin,
            region_id=None,
            region_scope="national",
            title="청년월세 지원",
            organization_name="국토교통부",
            deadline_kind="unknown",
        )
    )
    deduped = client.get("/support-programs", headers=auth_headers(token)).json()["items"]
    deduped_ids = {item["id"] for item in deduped}
    assert seed_ids["seed:gov24-youth-monthly-rent-2026"] in deduped_ids
    assert duplicate_api_id not in deduped_ids

    gyeonggi_token = token_for(user_factory())
    _profile(client, gyeonggi_token, _region_id(admin, "gyeonggi"))
    gyeonggi_items = client.get(
        "/support-programs", headers=auth_headers(gyeonggi_token)
    ).json()["items"]
    gyeonggi_ids = {item["id"] for item in gyeonggi_items}
    assert seed_ids["seed:gyeonggi-independent-youth-housing-2026"] in gyeonggi_ids
    assert seed_ids["seed:yongin-youth-brokerage-fee-2026"] not in gyeonggi_ids
    assert seed_ids["seed:yongin-youth-monthly-rent-2026"] not in gyeonggi_ids


def test_support_programs_ordering_housing_match_and_kst_close_boundary(
    client, admin, user_factory, token_for
):
    region_id = _create_region(
        admin, f"sort-{uuid4().hex[:8]}", f"정렬지역-{uuid4().hex[:6]}"
    )
    token = token_for(user_factory())
    _profile(client, token, region_id)
    today = admin.execute(
        "SELECT (now() AT TIME ZONE 'Asia/Seoul')::date AS value"
    ).fetchone()["value"]
    active_match = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="진행중 월세 공고",
            deadline_kind="fixed",
            deadline_date=today,
            deadline_text="오늘 마감",
            housing_types=("monthly_rent",),
        )
    )
    active_other = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="진행중 기타 공고",
            deadline_kind="fixed",
            deadline_date=today,
            deadline_text="오늘 마감",
        )
    )
    closed = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="마감 월세 공고",
            deadline_kind="fixed",
            deadline_date=date.fromordinal(today.toordinal() - 1),
            deadline_text="어제 마감",
            housing_types=("monthly_rent",),
        )
    )

    all_items = client.get("/support-programs", headers=auth_headers(token)).json()["items"]
    by_id = {item["id"]: item for item in all_items}
    assert by_id[active_match]["is_closed"] is False
    assert by_id[active_match]["housing_type_matched"] is True
    assert by_id[active_other]["is_closed"] is False
    assert by_id[active_other]["housing_type_matched"] is False
    assert by_id[closed]["is_closed"] is True

    test_order = [
        item["id"]
        for item in all_items
        if item["id"] in {active_match, active_other, closed}
    ]
    assert test_order == [active_match, active_other, closed]

    active = client.get(
        "/support-programs?status=active", headers=auth_headers(token)
    ).json()["items"]
    active_ids = {item["id"] for item in active}
    assert active_match in active_ids
    assert active_other in active_ids
    assert closed not in active_ids


def test_support_programs_distinguish_always_open_and_unknown_deadlines(
    client, admin, user_factory, token_for
):
    region_id = _create_region(
        admin, f"deadline-{uuid4().hex[:8]}", f"기한지역-{uuid4().hex[:6]}"
    )
    token = token_for(user_factory())
    _profile(client, token, region_id)
    always_open = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="상시 신청 공고",
            deadline_kind="always_open",
            deadline_text="상시 신청",
        )
    )
    unknown = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="기한 불명 공고",
            deadline_kind="unknown",
            deadline_text="접수기관 별 상이",
        )
    )

    items = client.get("/support-programs", headers=auth_headers(token)).json()["items"]
    by_id = {item["id"]: item for item in items}
    assert by_id[always_open]["deadline_kind"] == "always_open"
    assert by_id[always_open]["deadline_date"] is None
    assert by_id[always_open]["is_closed"] is False
    assert by_id[unknown]["deadline_kind"] == "unknown"
    assert by_id[unknown]["deadline_date"] is None
    assert by_id[unknown]["is_closed"] is False


def test_support_programs_empty_list_is_empty_not_fallback(
    client, admin, user_factory, token_for, empty_support_programs
):
    token = token_for(user_factory())
    _profile(client, token, _region_id(admin, "yongin"))

    response = client.get("/support-programs", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "limit": 5, "offset": 0, "has_more": False}


def test_seed_file_is_repeatable(admin):
    admin.execute(SEED_FILE.read_text())
    first = admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE external_id LIKE 'seed:%'"
    ).fetchone()["count"]
    admin.execute(SEED_FILE.read_text())
    second = admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE external_id LIKE 'seed:%'"
    ).fetchone()["count"]
    assert first == second


def test_support_programs_pagination_keeps_order_total_and_empty_overflow(
    client, admin, user_factory, token_for, empty_support_programs
):
    region_id = _create_region(
        admin, f"page-{uuid4().hex[:8]}", f"페이지지역-{uuid4().hex[:6]}"
    )
    token = token_for(user_factory())
    _profile(client, token, region_id)
    for index in range(3):
        _insert_program(
            admin,
            region_id=region_id,
            title=f"페이지 공고 {index}",
            deadline_kind="unknown",
        )

    ordered = [
        item["id"]
        for item in client.get(
            "/support-programs?limit=50", headers=auth_headers(token)
        ).json()["items"]
    ]
    assert len(ordered) == 3

    first = client.get(
        "/support-programs?limit=2&offset=0", headers=auth_headers(token)
    ).json()
    assert first["total"] == 3
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert first["has_more"] is True
    assert [item["id"] for item in first["items"]] == ordered[:2]

    second = client.get(
        "/support-programs?limit=2&offset=2", headers=auth_headers(token)
    ).json()
    assert second["total"] == 3
    assert second["has_more"] is False
    assert [item["id"] for item in second["items"]] == ordered[2:]

    overflow = client.get(
        "/support-programs?limit=2&offset=10", headers=auth_headers(token)
    ).json()
    assert overflow == {
        "items": [],
        "total": 3,
        "limit": 2,
        "offset": 10,
        "has_more": False,
    }

    assert (
        client.get(
            "/support-programs?limit=0", headers=auth_headers(token)
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/support-programs?limit=51", headers=auth_headers(token)
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/support-programs?offset=-1", headers=auth_headers(token)
        ).status_code
        == 422
    )


def test_support_programs_active_filter_total_counts_only_visible(
    client, admin, user_factory, token_for, empty_support_programs
):
    region_id = _create_region(
        admin, f"active-{uuid4().hex[:8]}", f"활성지역-{uuid4().hex[:6]}"
    )
    token = token_for(user_factory())
    _profile(client, token, region_id)
    today = admin.execute(
        "SELECT (now() AT TIME ZONE 'Asia/Seoul')::date AS value"
    ).fetchone()["value"]
    active = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="활성 공고",
            deadline_kind="fixed",
            deadline_date=today,
        )
    )
    closed = str(
        _insert_program(
            admin,
            region_id=region_id,
            title="마감 공고",
            deadline_kind="fixed",
            deadline_date=date.fromordinal(today.toordinal() - 1),
        )
    )

    body = client.get(
        "/support-programs?status=active&limit=1", headers=auth_headers(token)
    ).json()
    assert body["total"] == 1
    assert body["has_more"] is False
    assert [item["id"] for item in body["items"]] == [active]
    assert closed not in {item["id"] for item in body["items"]}

    all_items = client.get(
        "/support-programs?status=all&limit=50", headers=auth_headers(token)
    ).json()
    assert all_items["total"] == 2
    assert [item["id"] for item in all_items["items"]] == [active, closed]
