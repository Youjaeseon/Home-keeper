from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

GOV24_SERVICE_LIST_URL = "https://api.odcloud.kr/api/gov24/v3/serviceList"
PER_PAGE = 100
MAX_PAGES = 200
REQUEST_TIMEOUT_SECONDS = 15
SOURCE_ATTRIBUTION = "행정안전부 대한민국 공공서비스(혜택) 정보 · 공공데이터포털"

HOUSING_TITLE_KEYWORDS = (
    "주거",
    "주택",
    "전세",
    "월세",
    "전월세",
    "보증금",
    "중개보수",
    "중개수수료",
    "이사",
    "집수리",
    "슬레이트",
    "기숙사",
    "임대주택",
    "공공임대",
    "매입임대",
    "임대보증금",
)
NON_HOUSING_TITLE_KEYWORDS = (
    "축산",
    "농기계",
    "수산",
    "어업",
    "주택가격",
    "총조사",
    "통계조사",
    "특허",
    "지식재산",
)
HOUSING_TYPES = ("monthly_rent", "jeonse", "semi_jeonse", "owned")

PageFetcher = Callable[[int, int, str], dict[str, Any]]


class Gov24Error(RuntimeError):
    """Safe-to-display Gov24 failure; never includes the service key or request URL."""


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    matched: int
    upserted: int
    skipped: int
    skipped_reason: str | None = None


@dataclass(frozen=True)
class RegionRow:
    id: UUID
    name: str
    display_name: str


@dataclass(frozen=True)
class Gov24Program:
    external_id: str
    title: str
    summary: str
    organization_name: str
    region_scope: str
    region_id: UUID | None
    target_housing_types: tuple[str, ...]
    support_target: str
    support_content: str
    selection_criteria: str | None
    apply_method: str | None
    deadline_text: str | None
    deadline_date: date | None
    deadline_kind: str
    detail_url: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _int_value(value: Any, name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise Gov24Error(f"Gov24 응답의 {name} 형식이 올바르지 않습니다.") from error
    if number < 0:
        raise Gov24Error(f"Gov24 응답의 {name} 값이 올바르지 않습니다.")
    return number


def _encode_key(key: str) -> str:
    # data.go.kr keys are sometimes issued already URL-encoded.
    return key if "%" in key else urllib.parse.quote(key, safe="")


def _fetch_page(page: int, per_page: int, api_key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {"page": page, "perPage": per_page, "returnType": "JSON"}
    )
    url = f"{GOV24_SERVICE_LIST_URL}?{query}&serviceKey={_encode_key(api_key)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    for attempt in range(3):
        try:
            with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read()
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise Gov24Error("Gov24 응답이 JSON 형식이 아닙니다.") from error
            if not isinstance(payload, dict):
                raise Gov24Error("Gov24 응답 형식이 올바르지 않습니다.")
            code = payload.get("code")
            if code in (-401, 401, "-401", "401"):
                raise Gov24Error("Gov24 API 인증에 실패했습니다.")
            return payload
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise Gov24Error("Gov24 API 인증에 실패했습니다.") from None
            if error.code in (301, 302, 303, 307, 308):
                raise Gov24Error("Gov24 API의 예상하지 못한 리다이렉트를 차단했습니다.") from None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise Gov24Error(
                    f"Gov24 API 요청에 실패했습니다. (page {page})"
                ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if attempt == 2:
                raise Gov24Error(
                    f"Gov24 API 요청에 실패했습니다. (page {page})"
                ) from None
        time.sleep(0.5 * (attempt + 1))

    raise Gov24Error(f"Gov24 API 요청에 실패했습니다. (page {page})")


def _page_data(payload: dict[str, Any], page: int) -> tuple[list[dict[str, Any]], int]:
    data = payload.get("data")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise Gov24Error("Gov24 응답에 data 배열이 없습니다.")
    response_page = payload.get("page")
    if response_page is not None and _int_value(response_page, "page") != page:
        raise Gov24Error("Gov24 응답의 페이지 번호가 일치하지 않습니다.")
    return data, _int_value(payload.get("totalCount"), "totalCount")


def fetch_gov24_programs(
    api_key: str,
    *,
    page_fetcher: PageFetcher | None = None,
) -> list[dict[str, Any]]:
    """Fetch every list page before returning; any page failure aborts the sync."""
    if not api_key.strip():
        raise Gov24Error("GOV24_API_KEY is not set.")
    fetch = page_fetcher or _fetch_page
    first_data, total_count = _page_data(fetch(1, PER_PAGE, api_key), 1)
    if total_count == 0:
        return []
    page_count = math.ceil(total_count / PER_PAGE)
    if page_count > MAX_PAGES:
        raise Gov24Error("Gov24 응답 페이지 수가 허용 범위를 넘었습니다.")

    rows = list(first_data)
    for page in range(2, page_count + 1):
        page_rows, page_total = _page_data(fetch(page, PER_PAGE, api_key), page)
        if page_total != total_count:
            raise Gov24Error("Gov24 페이지별 전체 건수가 일치하지 않습니다.")
        rows.extend(page_rows)

    if len(rows) != total_count:
        raise Gov24Error("Gov24 응답의 전체 건수와 수집 건수가 일치하지 않습니다.")
    return rows


def classify_deadline(text: str | None) -> tuple[str, date | None]:
    """Parse only exact, unambiguous deadlines; everything else is unknown."""
    if not text or not text.strip():
        return "unknown", None

    normalized = " ".join(text.split())
    compact = normalized.replace(" ", "")
    if compact in {
        "상시",
        "상시신청",
        "상시접수",
        "연중",
        "연중신청",
        "연중접수",
    }:
        return "always_open", None

    match = re.fullmatch(
        r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*[일]?\.?"
        r"\s*(?:까지)?\s*(?:신청|접수|마감)?",
        normalized,
    )
    if not match:
        return "unknown", None
    try:
        deadline = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return "unknown", None
    return "fixed", deadline


def _load_regions(conn: psycopg.Connection) -> list[RegionRow]:
    rows = conn.execute(
        "SELECT id, name, display_name FROM regions ORDER BY display_name, id"
    ).fetchall()
    return [
        RegionRow(id=row["id"], name=row["name"], display_name=row["display_name"])
        for row in rows
    ]


def _resolve_region(
    record: dict[str, Any], regions: list[RegionRow]
) -> tuple[str, UUID | None] | None:
    """Resolve only an explicit central agency or an exact known local agency."""
    agency_type = _compact(_text(record, "소관기관유형"))
    if agency_type == "중앙행정기관":
        return "national", None

    agency_name = _text(record, "소관기관명") or _text(record, "접수기관명")
    compact_agency = _compact(agency_name)
    if not compact_agency:
        return None

    matches: dict[UUID, int] = {}
    for region in regions:
        full_name = _compact(region.display_name)
        short_name = _compact(region.display_name.split()[-1])
        candidates = {
            full_name,
            short_name,
            _compact(region.name),
            f"{full_name}청",
            f"{short_name}청",
        }
        candidates.discard("")
        if compact_agency in candidates:
            matches[region.id] = len(full_name)

    if not matches:
        return None
    longest = max(matches.values())
    winners = [region_id for region_id, length in matches.items() if length == longest]
    if len(winners) != 1:
        return None
    return "local", winners[0]


def _is_housing(record: dict[str, Any]) -> bool:
    """Use the title, not incidental words in a long eligibility description."""
    title = _compact(_text(record, "서비스명"))
    if not any(keyword in title for keyword in HOUSING_TITLE_KEYWORDS):
        return False
    return not any(keyword in title for keyword in NON_HOUSING_TITLE_KEYWORDS)


def _housing_types(record: dict[str, Any]) -> tuple[str, ...]:
    text = " ".join(
        filter(
            None,
            (
                _text(record, "서비스명"),
                _text(record, "서비스목적요약"),
                _text(record, "서비스목적"),
                _text(record, "지원대상"),
                _text(record, "지원내용"),
            ),
        )
    )
    tags: set[str] = set()
    remaining = text
    if "반전세" in remaining:
        tags.add("semi_jeonse")
        remaining = remaining.replace("반전세", " ")
    if "전월세" in remaining:
        tags.update(("monthly_rent", "jeonse"))
        remaining = remaining.replace("전월세", " ")
    if "월세" in remaining:
        tags.add("monthly_rent")
    if "전세" in remaining:
        tags.add("jeonse")
    if "자가가구" in remaining:
        tags.add("owned")
    return tuple(tag for tag in HOUSING_TYPES if tag in tags)


def _valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_gov24_program(
    record: dict[str, Any], regions: list[RegionRow]
) -> Gov24Program | None:
    if not _is_housing(record):
        return None

    external_id = _text(record, "서비스ID", "SVC_ID")
    title = _text(record, "서비스명")
    organization_name = _text(record, "소관기관명")
    support_target = _text(record, "지원대상")
    support_content = _text(record, "지원내용")
    detail_url = _text(record, "상세조회URL", "온라인신청사이트URL")
    if not all((external_id, title, organization_name, support_target, support_content)):
        return None
    if not _valid_http_url(detail_url):
        return None

    resolved_region = _resolve_region(record, regions)
    if resolved_region is None:
        return None

    summary = _text(record, "서비스목적요약", "서비스목적")
    if not summary:
        summary = support_content[:300]

    deadline_text = _text(record, "신청기한")
    deadline_kind, deadline_date = classify_deadline(deadline_text)
    region_scope, region_id = resolved_region
    return Gov24Program(
        external_id=external_id,
        title=title,
        summary=summary,
        organization_name=organization_name,
        region_scope=region_scope,
        region_id=region_id,
        target_housing_types=_housing_types(record),
        support_target=support_target,
        support_content=support_content,
        selection_criteria=_text(record, "선정기준"),
        apply_method=_text(record, "신청방법"),
        deadline_text=deadline_text,
        deadline_date=deadline_date,
        deadline_kind=deadline_kind,
        detail_url=detail_url,
    )


def _upsert_program(conn: psycopg.Connection, program: Gov24Program) -> None:
    conn.execute(
        """
        INSERT INTO support_programs (
            external_id,
            source,
            title,
            summary,
            organization_name,
            region_scope,
            region_id,
            target_housing_types,
            support_target,
            support_content,
            selection_criteria,
            apply_method,
            deadline_text,
            deadline_date,
            deadline_kind,
            detail_url,
            source_attribution,
            source_checked_at,
            synced_at,
            updated_at
        )
        VALUES (
            %s, 'gov24_api', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, now(), now(), now()
        )
        ON CONFLICT (external_id) DO UPDATE SET
            source = EXCLUDED.source,
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            organization_name = EXCLUDED.organization_name,
            region_scope = EXCLUDED.region_scope,
            region_id = EXCLUDED.region_id,
            target_housing_types = EXCLUDED.target_housing_types,
            support_target = EXCLUDED.support_target,
            support_content = EXCLUDED.support_content,
            selection_criteria = EXCLUDED.selection_criteria,
            apply_method = EXCLUDED.apply_method,
            deadline_text = EXCLUDED.deadline_text,
            deadline_date = EXCLUDED.deadline_date,
            deadline_kind = EXCLUDED.deadline_kind,
            detail_url = EXCLUDED.detail_url,
            source_attribution = EXCLUDED.source_attribution,
            source_checked_at = now(),
            synced_at = now(),
            updated_at = now()
        WHERE support_programs.source = 'gov24_api'
        """,
        (
            program.external_id,
            program.title,
            program.summary,
            program.organization_name,
            program.region_scope,
            program.region_id,
            list(program.target_housing_types),
            program.support_target,
            program.support_content,
            program.selection_criteria,
            program.apply_method,
            program.deadline_text,
            program.deadline_date,
            program.deadline_kind,
            program.detail_url,
            SOURCE_ATTRIBUTION,
        ),
    )


def sync_support_programs(
    conn: psycopg.Connection,
    api_key: str | None,
    *,
    page_fetcher: PageFetcher | None = None,
) -> SyncResult:
    """Fetch all pages first, then upsert. Caller owns the transaction/commit."""
    if not api_key or not api_key.strip():
        return SyncResult(
            fetched=0,
            matched=0,
            upserted=0,
            skipped=0,
            skipped_reason="GOV24_API_KEY is not set",
        )

    records = fetch_gov24_programs(api_key, page_fetcher=page_fetcher)
    regions = _load_regions(conn)
    candidates = [
        candidate
        for record in records
        if (candidate := build_gov24_program(record, regions)) is not None
    ]
    with conn.transaction():
        for candidate in candidates:
            _upsert_program(conn, candidate)

    return SyncResult(
        fetched=len(records),
        matched=len(candidates),
        upserted=len(candidates),
        skipped=len(records) - len(candidates),
    )


def main() -> int:
    api_key = os.environ.get("GOV24_API_KEY", "").strip()
    if not api_key:
        print("GOV24_API_KEY is not set; sync skipped. Existing seed/cache is unchanged.")
        return 0

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is not set; sync skipped.", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=5,
            application_name="career-pair-support-sync",
        ) as conn:
            with conn.transaction():
                result = sync_support_programs(conn, api_key)
    except (Gov24Error, psycopg.Error) as error:
        print(f"support program sync failed: {error}", file=sys.stderr)
        return 1

    print(
        "support program sync complete: "
        f"fetched={result.fetched}, matched={result.matched}, "
        f"upserted={result.upserted}, skipped={result.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
