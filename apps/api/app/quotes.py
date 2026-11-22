"""Open quote requests and provider proposals.

One record can have one open request. Region and work type matching decides
which providers may see/propose; requesters see every proposal, providers see
only their own. Photo paths are signed on read through the private bucket.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path
from psycopg.types.json import Jsonb

from app import storage
from app.auth import get_current_user
from app.db import read_transaction, transaction
from app.errors import (
    invalid_request,
    not_found,
    request_already_open,
    request_not_open,
    proposal_already_exists,
    proposal_not_pending,
    diagnosis_required,
)
from app.schemas import (
    ErrorResponse,
    QuoteProposalCreateRequest,
    QuoteProposalOut,
    QuoteRequestCreateRequest,
    QuoteRequestDetailOut,
    QuoteRequestSummary,
)

_INSPECTION_WORK_TYPE = "원인 점검"

_UNAUTHORIZED_RESPONSE = {
    "model": ErrorResponse,
    "description": "인증 실패 또는 만료",
}
_NOT_FOUND_RESPONSE = {
    "model": ErrorResponse,
    "description": "요청서·기록·제안서를 찾을 수 없거나 접근 권한이 없음",
}
_CONFLICT_RESPONSE = {
    "model": ErrorResponse,
    "description": "진단 없음, 중복 공개·제안, 마감·취소된 요청서",
}
_VALIDATION_RESPONSE = {
    "model": ErrorResponse,
    "description": "요청 형식·가격 범위·지역·작업 종류 검증 실패",
}

router = APIRouter(
    tags=["quote-requests"],
    responses={401: _UNAUTHORIZED_RESPONSE},
)

_REQUEST_BASE = """
    SELECT
        request.*,
        region.display_name AS region_name,
        work_type.name AS work_type_name,
        requester_profile.nickname AS requester_nickname
"""
_REQUEST_FROM = """
    FROM quote_requests AS request
    JOIN regions AS region ON region.id = request.region_id
    JOIN work_types AS work_type ON work_type.id = request.work_type_id
    LEFT JOIN profiles AS requester_profile ON requester_profile.user_id = request.requester_id
"""

_PROPOSAL_SELECT = """
    SELECT
        proposal.id AS proposal_id,
        proposal.request_id,
        proposal.provider_id,
        proposal.min_price,
        proposal.max_price,
        proposal.memo,
        proposal.status,
        proposal.created_at,
        provider.name,
        provider.phone,
        provider.rating,
        provider.review_count,
        provider.description,
        (provider.account_user_id IS NOT NULL) AS chat_available,
        COALESCE(
            (
                SELECT jsonb_agg(service_region.display_name ORDER BY service_region.display_name)
                FROM provider_regions AS provider_region
                JOIN regions AS service_region ON service_region.id = provider_region.region_id
                WHERE provider_region.provider_id = provider.id
            ),
            '[]'::jsonb
        ) AS region_names,
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'work_type_id', work_type.id,
                        'name', work_type.name
                    )
                    ORDER BY work_type.name, work_type.id
                )
                FROM provider_work_types AS provider_work
                JOIN work_types AS work_type
                  ON work_type.id = provider_work.work_type_id
                WHERE provider_work.provider_id = provider.id
            ),
            '[]'::jsonb
        ) AS specialty_work_types
    FROM quote_proposals AS proposal
    JOIN providers AS provider ON provider.id = proposal.provider_id
"""


def _provider_for_user(conn, user_id: UUID) -> dict | None:
    return conn.execute(
        "SELECT * FROM providers WHERE account_user_id = %s", (user_id,)
    ).fetchone()


def _require_requester(conn, user_id: UUID) -> None:
    if _provider_for_user(conn, user_id) is not None:
        raise invalid_request("업체 계정은 요청인 전용 기능을 사용할 수 없습니다.")


def _summary(row: dict, **overrides) -> dict:
    return {
        "request_id": row["id"],
        "record_id": row["record_id"],
        "region_id": row["region_id"],
        "region_name": row["region_name"],
        "work_type_id": row["work_type_id"],
        "work_type_name": row["work_type_name"],
        "requester_nickname": row.get("requester_nickname"),
        "address": row["address"],
        "location": row["location"],
        "material": row["material"],
        "memo": row["memo"],
        "photos": storage.signed_photos(row["photo_files"]),
        "severity_score": row["severity_score"],
        "severity_level": row["severity_level"],
        "suspected_types": row["suspected_types"],
        "status": row["status"],
        "accepted_proposal_id": row["accepted_proposal_id"],
        "proposal_count": overrides.pop("proposal_count", 0),
        "my_proposal_id": overrides.pop("my_proposal_id", None),
        "my_proposal_status": overrides.pop("my_proposal_status", None),
        "created_at": row["created_at"],
        **overrides,
    }


def _proposal_out(row: dict) -> dict:
    return {
        "proposal_id": row["proposal_id"],
        "created_at": row["created_at"],
        "provider": {
            "provider_id": row["provider_id"],
            "name": row["name"],
            "phone": row["phone"],
            "rating": row["rating"],
            "review_count": row["review_count"],
            "description": row["description"],
            "specialty_work_types": row["specialty_work_types"],
            "region_names": row["region_names"],
            "chat_available": row["chat_available"],
            "is_sample": False,
        },
        "min_price": row["min_price"],
        "max_price": row["max_price"],
        "memo": row["memo"],
        "status": row["status"],
    }


def _request_row(conn, request_id: UUID) -> dict:
    row = conn.execute(
        _REQUEST_BASE + _REQUEST_FROM + " WHERE request.id = %s", (request_id,)
    ).fetchone()
    if row is None:
        raise not_found("견적 요청서를 찾을 수 없습니다.")
    return row


def _detail(conn, request_id: UUID, user_id: UUID) -> dict:
    row = _request_row(conn, request_id)
    provider = _provider_for_user(conn, user_id)
    owner = row["requester_id"] == user_id

    proposal_access = None
    if provider is not None:
        proposal_access = conn.execute(
            """
            SELECT id, status FROM quote_proposals
            WHERE request_id = %s AND provider_id = %s
            """,
            (request_id, provider["id"]),
        ).fetchone()

    matched = False
    if provider is not None and row["status"] == "open":
        matched = conn.execute(
            """
            SELECT 1
            FROM provider_regions AS provider_region
            JOIN provider_work_types AS provider_work
              ON provider_work.provider_id = provider_region.provider_id
            WHERE provider_region.provider_id = %s
              AND provider_region.region_id = %s
              AND provider_work.work_type_id = %s
            """,
            (provider["id"], row["region_id"], row["work_type_id"]),
        ).fetchone() is not None

    if not owner and not matched and proposal_access is None:
        raise not_found("견적 요청서를 찾을 수 없습니다.")

    if owner:
        proposals = [
            _proposal_out(item)
            for item in conn.execute(
                _PROPOSAL_SELECT
                + " WHERE proposal.request_id = %s ORDER BY proposal.created_at DESC, proposal.id DESC",
                (request_id,),
            ).fetchall()
        ]
        proposal_count = len(proposals)
        my_proposal_id = None
        my_proposal_status = None
    else:
        proposals = [
            _proposal_out(item)
            for item in conn.execute(
                _PROPOSAL_SELECT
                + " WHERE proposal.request_id = %s AND proposal.provider_id = %s"
                " ORDER BY proposal.created_at DESC, proposal.id DESC",
                (request_id, provider["id"]),
            ).fetchall()
        ]
        # Do not expose how many competing proposals exist to providers.
        proposal_count = 0
        my_proposal_id = proposal_access["id"] if proposal_access else None
        my_proposal_status = proposal_access["status"] if proposal_access else None

    return {
        **_summary(
            row,
            proposal_count=proposal_count,
            my_proposal_id=my_proposal_id,
            my_proposal_status=my_proposal_status,
        ),
        "proposals": proposals,
    }


@router.post(
    "/quote-requests",
    response_model=QuoteRequestDetailOut,
    summary="견적 요청서 공개",
    description=(
        "본인 하자 기록을 지역·특화 분야 기반 1:N 공개 견적 요청서로 등록합니다.\n\n"
        "- 요청인 계정 전용입니다. 업체 계정은 `422`입니다.\n"
        "- 진단이 없으면 `409`(`diagnosis_required`), 같은 기록에 진행 중 요청서가 있으면 `409`(`request_already_open`)입니다.\n"
        "- 지역은 요청값 → 기록 지역 → 프로필 거주 지역, 작업 종류는 요청값 → 진단 추천 작업 → `원인 점검` 순으로 결정합니다.\n"
        "- 사진 Storage 경로와 진단 심각도·의심 유형을 발행 시점 스냅샷으로 저장합니다."
    ),
    responses={404: _NOT_FOUND_RESPONSE, 409: _CONFLICT_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def create_quote_request(
    body: Annotated[QuoteRequestCreateRequest, Body()],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        _require_requester(conn, owner_id)
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
            (body.record_id, owner_id),
        ).fetchone()
        if record is None:
            raise not_found("기록을 찾을 수 없습니다.")
        if record["diagnosis"] is None:
            raise diagnosis_required()
        diagnosis = record["diagnosis"]

        region_id = body.region_id or record["region_id"]
        if region_id is None:
            profile = conn.execute(
                "SELECT region_id FROM profiles WHERE user_id = %s", (owner_id,)
            ).fetchone()
            region_id = profile["region_id"] if profile else None
        if region_id is None or conn.execute(
            "SELECT 1 FROM regions WHERE id = %s", (region_id,)
        ).fetchone() is None:
            raise invalid_request("선택한 지역을 찾을 수 없습니다.")

        work_type_id = body.work_type_id or diagnosis.get("work_type_id")
        if body.work_type_id is not None:
            if conn.execute(
                "SELECT 1 FROM work_types WHERE id = %s", (body.work_type_id,)
            ).fetchone() is None:
                raise invalid_request("선택한 작업 종류를 찾을 수 없습니다.")
        elif work_type_id is None or conn.execute(
            "SELECT 1 FROM work_types WHERE id = %s", (work_type_id,)
        ).fetchone() is None:
            inspection = conn.execute(
                "SELECT id FROM work_types WHERE name = %s", (_INSPECTION_WORK_TYPE,)
            ).fetchone()
            if inspection is None:
                raise invalid_request("작업 종류를 찾을 수 없습니다.")
            work_type_id = inspection["id"]

        location = (record["location"] or "").strip()
        if not location:
            raise invalid_request("하자 위치가 없어 견적 요청서를 만들 수 없습니다.")
        memo = (body.memo if body.memo is not None else record["symptoms"]) or ""
        memo = memo.strip() or None
        address = (body.address or "").strip() or None

        created = conn.execute(
            """
            INSERT INTO quote_requests (
                record_id, requester_id, region_id, work_type_id, address,
                location, material, memo, photo_files, severity_score,
                severity_level, suspected_types
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                record["id"],
                owner_id,
                region_id,
                work_type_id,
                address,
                location,
                record["material"],
                memo,
                Jsonb(record["photo_files"]),
                diagnosis.get("severity_score"),
                diagnosis.get("severity_level"),
                diagnosis.get("suspected_types") or [],
            ),
        ).fetchone()
        if created is None:
            raise request_already_open()
        request_id = created["id"]

    with read_transaction() as conn:
        return _detail(conn, request_id, owner_id)


@router.get(
    "/quote-requests",
    response_model=list[QuoteRequestSummary],
    summary="견적 요청서 목록",
    description=(
        "역할에 따라 목록이 달라집니다.\n\n"
        "- 요청인: 본인이 보낸 요청서를 최신순으로 반환하며 `proposal_count`와 사진 Signed URL을 포함합니다.\n"
        "- 업체: 출장 지역과 특화 분야가 모두 맞는 진행 중 요청서와 본인이 이미 제안서를 보낸 요청서만 반환하며 `my_proposal_id`·`my_proposal_status`를 포함합니다.\n"
        "- 업체에게는 경쟁 업체 제안서 수를 노출하지 않습니다."
    ),
)
def list_quote_requests(owner_id: UUID = Depends(get_current_user)):
    with read_transaction() as conn:
        provider = _provider_for_user(conn, owner_id)
        if provider is None:
            rows = conn.execute(
                _REQUEST_BASE
                + """
                , (
                    SELECT count(*) FROM quote_proposals AS proposal
                    WHERE proposal.request_id = request.id
                ) AS proposal_count
                """
                + _REQUEST_FROM
                + """
                WHERE request.requester_id = %s
                ORDER BY request.created_at DESC, request.id DESC
                """,
                (owner_id,),
            ).fetchall()
            return [
                _summary(row, proposal_count=row["proposal_count"]) for row in rows
            ]

        rows = conn.execute(
            _REQUEST_BASE
            + """
            , mine.id AS my_proposal_id,
              mine.status AS my_proposal_status
            """
            + _REQUEST_FROM
            + """
            LEFT JOIN quote_proposals AS mine
              ON mine.request_id = request.id AND mine.provider_id = %s
            WHERE (
                mine.id IS NOT NULL
                OR (
                    request.status = 'open'
                    AND EXISTS (
                        SELECT 1 FROM provider_regions AS provider_region
                        WHERE provider_region.provider_id = %s
                          AND provider_region.region_id = request.region_id
                    )
                    AND EXISTS (
                        SELECT 1 FROM provider_work_types AS provider_work
                        WHERE provider_work.provider_id = %s
                          AND provider_work.work_type_id = request.work_type_id
                    )
                )
            )
            ORDER BY request.created_at DESC, request.id DESC
            """,
            (provider["id"], provider["id"], provider["id"]),
        ).fetchall()
        return [
            _summary(
                row,
                proposal_count=0,
                my_proposal_id=row["my_proposal_id"],
                my_proposal_status=row["my_proposal_status"],
            )
            for row in rows
        ]


@router.get(
    "/quote-requests/{request_id}",
    response_model=QuoteRequestDetailOut,
    summary="견적 요청서 상세",
    description=(
        "요청인 본인, 지역·특화 분야가 모두 맞는 업체, 이미 제안서를 보낸 업체만 조회할 수 있습니다.\n\n"
        "- 요청인에게는 도착한 모든 제안서를, 업체에게는 본인 제안서만 반환합니다.\n"
        "- 사진은 비공개 Storage의 단기 Signed URL로 반환합니다.\n"
        "- 권한이 없는 사용자·타 지역·타 분야 업체는 `404`입니다."
    ),
    responses={404: _NOT_FOUND_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def get_quote_request(
    request_id: Annotated[UUID, Path(description="조회할 견적 요청서 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        return _detail(conn, request_id, owner_id)


@router.post(
    "/quote-requests/{request_id}/proposals",
    response_model=QuoteProposalOut,
    summary="업체 제안서 제출",
    description=(
        "지역과 특화 분야가 모두 맞는 업체가 진행 중 요청서에 제안서를 1건 제출합니다.\n\n"
        "- 요청인 계정은 `422`, 비매칭 업체는 `404`입니다.\n"
        "- 마감·취소된 요청서는 `409`(`request_not_open`), 같은 요청서에 이미 제출했으면 `409`(`proposal_already_exists`)입니다.\n"
        "- 최소 금액은 0원 이상, 최대 금액은 최소 금액 이상이어야 하며 메모는 공백 없이 2000자 이하입니다."
    ),
    responses={404: _NOT_FOUND_RESPONSE, 409: _CONFLICT_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def create_quote_proposal(
    request_id: Annotated[UUID, Path(description="제안서를 보낼 견적 요청서 UUID.")],
    body: Annotated[QuoteProposalCreateRequest, Body()],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        provider = _provider_for_user(conn, owner_id)
        if provider is None:
            raise invalid_request("업체 계정만 제안서를 보낼 수 있습니다.")

        request = conn.execute(
            "SELECT * FROM quote_requests WHERE id = %s FOR UPDATE", (request_id,)
        ).fetchone()
        if request is None:
            raise not_found("견적 요청서를 찾을 수 없습니다.")
        matched = conn.execute(
            """
            SELECT 1
            FROM provider_regions AS provider_region
            JOIN provider_work_types AS provider_work
              ON provider_work.provider_id = provider_region.provider_id
            WHERE provider_region.provider_id = %s
              AND provider_region.region_id = %s
              AND provider_work.work_type_id = %s
            """,
            (provider["id"], request["region_id"], request["work_type_id"]),
        ).fetchone()
        if matched is None:
            raise not_found("견적 요청서를 찾을 수 없습니다.")
        if request["status"] != "open":
            raise request_not_open()

        created = conn.execute(
            """
            INSERT INTO quote_proposals
                (request_id, provider_id, min_price, max_price, memo)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (request_id, provider["id"], body.min_price, body.max_price, body.memo),
        ).fetchone()
        if created is None:
            raise proposal_already_exists()

        proposal = conn.execute(
            _PROPOSAL_SELECT + " WHERE proposal.id = %s", (created["id"],)
        ).fetchone()
    return _proposal_out(proposal)


@router.post(
    "/quote-requests/{request_id}/proposals/{proposal_id}/accept",
    response_model=QuoteRequestDetailOut,
    summary="제안서 수락",
    description=(
        "요청인이 도착한 제안서 1건을 수락합니다.\n\n"
        "- 요청서 소유자만 호출할 수 있으며, 진행 중이 아니면 `409`(`request_not_open`)입니다.\n"
        "- 수락 제안서는 `accepted`, 나머지 대기 제안서는 `rejected`, 요청서는 `accepted`로 원자 처리합니다.\n"
        "- 동시 수락 경쟁에서는 한 요청만 성공하고 나머지는 `409`입니다."
    ),
    responses={404: _NOT_FOUND_RESPONSE, 409: _CONFLICT_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def accept_quote_proposal(
    request_id: Annotated[UUID, Path(description="수락할 견적 요청서 UUID.")],
    proposal_id: Annotated[UUID, Path(description="수락할 제안서 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        request = conn.execute(
            "SELECT * FROM quote_requests WHERE id = %s AND requester_id = %s FOR UPDATE",
            (request_id, owner_id),
        ).fetchone()
        if request is None:
            raise not_found("견적 요청서를 찾을 수 없습니다.")
        if request["status"] != "open":
            raise request_not_open()

        proposal = conn.execute(
            """
            SELECT id, status FROM quote_proposals
            WHERE id = %s AND request_id = %s FOR UPDATE
            """,
            (proposal_id, request_id),
        ).fetchone()
        if proposal is None:
            raise not_found("제안서를 찾을 수 없습니다.")
        if proposal["status"] != "pending":
            raise proposal_not_pending()

        conn.execute(
            "UPDATE quote_proposals SET status = 'accepted', updated_at = now() WHERE id = %s",
            (proposal_id,),
        )
        conn.execute(
            """
            UPDATE quote_proposals
            SET status = 'rejected', updated_at = now()
            WHERE request_id = %s AND id <> %s AND status = 'pending'
            """,
            (request_id, proposal_id),
        )
        conn.execute(
            """
            UPDATE quote_requests
            SET status = 'accepted', accepted_proposal_id = %s,
                accepted_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (proposal_id, request_id),
        )

    with read_transaction() as conn:
        return _detail(conn, request_id, owner_id)


@router.post(
    "/quote-requests/{request_id}/cancel",
    response_model=QuoteRequestDetailOut,
    summary="견적 요청서 취소",
    description=(
        "요청인이 진행 중 요청서를 취소하고 대기 중 제안서를 모두 `rejected`로 마감합니다.\n\n"
        "- 요청서 소유자만 호출할 수 있으며, 이미 수락·취소된 요청서는 `409`(`request_not_open`)입니다."
    ),
    responses={404: _NOT_FOUND_RESPONSE, 409: _CONFLICT_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def cancel_quote_request(
    request_id: Annotated[UUID, Path(description="취소할 견적 요청서 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        request = conn.execute(
            "SELECT * FROM quote_requests WHERE id = %s AND requester_id = %s FOR UPDATE",
            (request_id, owner_id),
        ).fetchone()
        if request is None:
            raise not_found("견적 요청서를 찾을 수 없습니다.")
        if request["status"] != "open":
            raise request_not_open()

        conn.execute(
            "UPDATE quote_requests SET status = 'cancelled', updated_at = now() WHERE id = %s",
            (request_id,),
        )
        conn.execute(
            """
            UPDATE quote_proposals
            SET status = 'rejected', updated_at = now()
            WHERE request_id = %s AND status = 'pending'
            """,
            (request_id,),
        )

    with read_transaction() as conn:
        return _detail(conn, request_id, owner_id)
