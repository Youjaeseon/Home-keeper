from datetime import date
from uuid import uuid4

import pytest

from app import support_sync
from app.support_sync import (
    Gov24Error,
    RegionRow,
    _categories,
    build_gov24_program,
    classify_deadline,
    fetch_gov24_programs,
    sync_support_programs,
)


def _record(**overrides):
    value = {
        "서비스ID": "test-gov24-1",
        "서비스명": "청년월세 지원",
        "서비스목적요약": "청년의 주거비 부담 경감",
        "서비스분야": "주거",
        "소관기관명": "국토교통부",
        "소관기관유형": "중앙행정기관",
        "지원대상": "무주택 청년",
        "지원내용": "월세를 최대 20만원 지원",
        "신청방법": "복지로 온라인 신청",
        "신청기한": "2026-06-30까지",
        "상세조회URL": "https://example.com/program/1",
    }
    value.update(overrides)
    return value


def _paged_fetcher(records):
    calls = []

    def fetch(page, per_page, api_key):
        calls.append((page, per_page, api_key))
        start = (page - 1) * per_page
        return {
            "page": page,
            "perPage": per_page,
            "totalCount": len(records),
            "currentCount": len(records[start : start + per_page]),
            "data": records[start : start + per_page],
        }

    return fetch, calls


def test_classify_deadline_only_accepts_clear_deadlines():
    assert classify_deadline("2026. 10. 31.까지") == ("fixed", date(2026, 10, 31))
    assert classify_deadline("2026-10-31") == ("fixed", date(2026, 10, 31))
    assert classify_deadline("2026년 10월 31일까지") == (
        "fixed",
        date(2026, 10, 31),
    )
    assert classify_deadline("상시 신청") == ("always_open", None)
    assert classify_deadline("연중") == ("always_open", None)
    assert classify_deadline("접수기관 별 상이") == ("unknown", None)
    assert classify_deadline("매년 하반기 접수") == ("unknown", None)
    assert classify_deadline("2026. 10. 1. ~ 10. 31.") == ("unknown", None)
    assert classify_deadline("2026. 13. 01.") == ("unknown", None)
    assert classify_deadline(None) == ("unknown", None)


def test_classify_deadline_uses_gov24_deadline_type():
    assert classify_deadline("상시신청", "상시신청") == ("always_open", None)
    assert classify_deadline("2026.05.04~2026.05.20", "기간설정") == (
        "fixed",
        date(2026, 5, 20),
    )
    assert classify_deadline(
        "2026.05.04~2026.05.20, 2026.09.01~2026.09.30", "기간설정"
    ) == ("unknown", None)
    assert classify_deadline("2026.12.31까지", "접수기관별상이") == (
        "unknown",
        None,
    )
    assert classify_deadline("2026.12.31까지", "직접입력") == (
        "fixed",
        date(2026, 12, 31),
    )
    assert classify_deadline(
        "2026-01-01 00:00 ~ 2026-12-31 00:00", "직접입력"
    ) == ("fixed", date(2026, 12, 31))


def test_categories_use_title_and_summary_keywords():
    assert _categories({"서비스명": "청년월세 지원"}) == ("monthly_rent_support",)
    assert _categories({"서비스명": "버팀목전세자금대출"}) == ("deposit_loan",)
    assert _categories({"서비스명": "부동산 중개보수 감면"}) == ("brokerage_fee",)
    assert _categories({"서비스명": "농촌취약계층주거개선"}) == ("repair",)
    assert _categories(
        {"서비스명": "월세자금보증", "서비스목적요약": "보증"}
    ) == ("monthly_rent_support", "deposit_loan")
    assert _categories({"서비스명": "청년 정책"}) == ("other",)


def test_build_gov24_program_resolves_only_explicit_regions():
    regions = [
        RegionRow(uuid4(), "yongin", "경기도 용인시"),
        RegionRow(uuid4(), "gyeonggi", "경기도"),
    ]
    national = build_gov24_program(_record(), regions)
    assert national is not None
    assert national.region_scope == "national"
    assert national.region_id is None
    assert national.target_housing_types == ("monthly_rent",)
    assert national.categories == ("monthly_rent_support", "housing_cost")
    assert national.deadline_kind == "fixed"
    assert national.deadline_date == date(2026, 6, 30)

    national_with_local_reception = build_gov24_program(
        _record(접수기관="용인시청"), regions
    )
    assert national_with_local_reception is not None
    assert national_with_local_reception.region_scope == "national"

    yongin = build_gov24_program(
        _record(
            서비스ID="test-gov24-yongin",
            소관기관명="용인시",
            소관기관유형="지방자치단체",
            접수기관="용인시청",
        ),
        regions,
    )
    assert yongin is not None
    assert yongin.region_scope == "local"
    assert yongin.region_id == regions[0].id

    gyeonggi = build_gov24_program(
        _record(
            서비스ID="test-gov24-gyeonggi",
            소관기관명="경기도",
            소관기관유형="광역시도",
        ),
        regions,
    )
    assert gyeonggi is not None
    assert gyeonggi.region_scope == "local"
    assert gyeonggi.region_id == regions[1].id

    assert (
        build_gov24_program(
            _record(
                서비스ID="test-gov24-siheung",
                소관기관명="경기도 시흥시",
                소관기관유형="시군구",
            ),
            regions,
        )
        is None
    )

    assert (
        build_gov24_program(
            _record(소관기관명="알 수 없는 기관", 소관기관유형="공공기관"),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(서비스명="지식재산거래 지원(특허기술 거래 중개 서비스 지원)"),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(서비스명="인구주택총조사 통계조사원 일자리 제공"),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(서비스명="개별주택가격 카카오톡 알리미 서비스 신청"),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(서비스명="농기계 임대 지원"),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(
                서비스명="청년 문화 지원",
                서비스목적요약="문화 활동 지원",
                서비스분야="문화",
                지원대상="청년",
                지원내용="문화 활동",
            ),
            regions,
        )
        is None
    )
    assert (
        build_gov24_program(
            _record(상세조회URL="ftp://example.com/program"), regions
        )
        is None
    )


def test_fetch_gov24_programs_reads_all_pages(monkeypatch):
    monkeypatch.setattr(support_sync, "PER_PAGE", 2)
    records = [_record(서비스ID=f"test-{index}") for index in range(3)]
    fetch, calls = _paged_fetcher(records)

    result = fetch_gov24_programs("test-key", page_fetcher=fetch)

    assert [record["서비스ID"] for record in result] == [
        "test-0",
        "test-1",
        "test-2",
    ]
    assert [call[0] for call in calls] == [1, 2]
    assert all(call[2] == "test-key" for call in calls)


def test_fetch_gov24_programs_rejects_partial_or_malformed_pages(monkeypatch):
    monkeypatch.setattr(support_sync, "PER_PAGE", 2)

    def partial(page, per_page, api_key):
        if page == 2:
            raise Gov24Error("page two failed")
        return {
            "page": page,
            "perPage": per_page,
            "totalCount": 4,
            "data": [_record(서비스ID="test-1"), _record(서비스ID="test-2")],
        }

    with pytest.raises(Gov24Error):
        fetch_gov24_programs("test-key", page_fetcher=partial)

    def too_short(page, per_page, api_key):
        return {
            "page": page,
            "perPage": per_page,
            "totalCount": 3,
            "data": [_record(서비스ID="test-1")],
        }

    with pytest.raises(Gov24Error):
        fetch_gov24_programs("test-key", page_fetcher=too_short)

    with pytest.raises(Gov24Error):
        fetch_gov24_programs(
            "test-key",
            page_fetcher=lambda page, per_page, key: {"data": "not-a-list"},
        )


def test_sync_without_api_key_is_skipped_without_network(admin):
    calls = []

    def fetch(page, per_page, api_key):
        calls.append(page)
        return {}

    before = admin.execute(
        "SELECT count(*) AS count FROM support_programs"
    ).fetchone()["count"]
    result = sync_support_programs(admin, None, page_fetcher=fetch)
    after = admin.execute(
        "SELECT count(*) AS count FROM support_programs"
    ).fetchone()["count"]

    assert result.skipped_reason == "GOV24_API_KEY is not set"
    assert result.upserted == 0
    assert calls == []
    assert before == after


def test_sync_upserts_complete_housing_pages_and_is_idempotent(admin):
    records = [
        _record(서비스ID="test-gov24-national"),
        _record(
            서비스ID="test-gov24-yongin",
            서비스명="용인 청년월세",
            소관기관명="용인시",
            소관기관유형="지방자치단체",
            접수기관="용인시청",
            신청기한="상시 신청",
        ),
        _record(
            서비스ID="test-gov24-culture",
            서비스명="청년 문화 지원",
            서비스목적요약="문화 활동 지원",
            서비스분야="문화",
            지원대상="청년",
            지원내용="문화 활동",
        ),
        _record(
            서비스ID="test-gov24-bad-url",
            상세조회URL="javascript:alert(1)",
        ),
    ]
    fetch, _ = _paged_fetcher(records)

    with admin.transaction(force_rollback=True):
        first = sync_support_programs(admin, "test-key", page_fetcher=fetch)
        second = sync_support_programs(admin, "test-key", page_fetcher=fetch)

        rows = {
            row["external_id"]: row
            for row in admin.execute(
                """
                SELECT external_id, region_scope, region_id, target_housing_types,
                       categories, deadline_kind, deadline_text, source,
                       source_checked_at, synced_at
                FROM support_programs
                WHERE external_id LIKE 'test-gov24-%'
                """
            ).fetchall()
        }

    assert first.fetched == 4
    assert first.matched == 2
    assert first.upserted == 2
    assert first.skipped == 2
    assert second.upserted == 2
    assert set(rows) == {"test-gov24-national", "test-gov24-yongin"}
    assert rows["test-gov24-national"]["region_scope"] == "national"
    assert rows["test-gov24-national"]["region_id"] is None
    assert rows["test-gov24-national"]["target_housing_types"] == ["monthly_rent"]
    assert rows["test-gov24-national"]["categories"] == [
        "monthly_rent_support",
        "housing_cost",
    ]
    assert rows["test-gov24-national"]["deadline_kind"] == "fixed"
    assert rows["test-gov24-national"]["source"] == "gov24_api"
    assert rows["test-gov24-national"]["source_checked_at"]
    assert rows["test-gov24-national"]["synced_at"]
    assert rows["test-gov24-yongin"]["region_scope"] == "local"
    assert rows["test-gov24-yongin"]["region_id"] is not None
    assert rows["test-gov24-yongin"]["deadline_kind"] == "always_open"
    assert rows["test-gov24-yongin"]["deadline_text"] == "상시 신청"
    assert admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE external_id LIKE 'test-gov24-%'"
    ).fetchone()["count"] == 0


def test_sync_failure_preserves_existing_data(admin, monkeypatch):
    monkeypatch.setattr(support_sync, "PER_PAGE", 2)
    before = admin.execute(
        "SELECT count(*) AS count FROM support_programs"
    ).fetchone()["count"]

    def failing(page, per_page, api_key):
        if page == 2:
            raise Gov24Error("page two failed")
        return {
            "page": page,
            "perPage": per_page,
            "totalCount": 3,
            "data": [
                _record(서비스ID="test-partial-1"),
                _record(서비스ID="test-partial-2"),
            ],
        }

    with pytest.raises(Gov24Error):
        sync_support_programs(admin, "test-key", page_fetcher=failing)

    after = admin.execute(
        "SELECT count(*) AS count FROM support_programs"
    ).fetchone()["count"]
    assert before == after
    assert admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE external_id LIKE 'test-partial-%'"
    ).fetchone()["count"] == 0
