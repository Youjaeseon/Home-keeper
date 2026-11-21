"""Provider search and detail.

Real candidates come from providers linked to the requested region (and, when
given, work type). Sample candidates are returned only when the real search
succeeded and returned nothing; database errors surface as 500 instead of
falling back. Ranking is rating-first.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.auth import get_current_user
from app.db import read_transaction
from app.errors import invalid_request, not_found
from app.schemas import (
    ErrorResponse,
    ProviderDetailOut,
    ProviderSearchResponse,
    WorkTypeOut,
)

_UNAUTHORIZED_RESPONSE = {
    "model": ErrorResponse,
    "description": "인증 실패 또는 만료",
    "content": {
        "application/json": {
            "examples": {
                "unauthorized": {
                    "summary": "유효하지 않거나 누락된 액세스 토큰",
                    "value": {
                        "code": "unauthorized",
                        "message": "액세스 토큰이 유효하지 않거나 만료되었습니다.",
                    },
                }
            }
        }
    },
}

_VALIDATION_ERROR_RESPONSE = {
    "model": ErrorResponse,
    "description": "존재하지 않는 지역·작업 종류 또는 쿼리 형식 오류",
    "content": {
        "application/json": {
            "examples": {
                "invalid_request": {
                    "summary": "등록되지 않은 지역 또는 작업 종류",
                    "value": {
                        "code": "invalid_request",
                        "message": "선택한 지역을 찾을 수 없습니다.",
                    },
                }
            }
        }
    },
}

_PROVIDER_NOT_FOUND_RESPONSE = {
    "model": ErrorResponse,
    "description": "존재하지 않거나 시연용 샘플인 업체",
    "content": {
        "application/json": {
            "examples": {
                "provider_not_found": {
                    "summary": "없는 업체",
                    "value": {
                        "code": "not_found",
                        "message": "업체를 찾을 수 없습니다.",
                    },
                }
            }
        }
    },
}

# Demo candidates. They never exist in the providers table and carry no real
# contact details, so nothing is invented or mixed into real search results.
_SAMPLE_PROVIDERS = [
    {
        "provider_id": "00000000-0000-4000-8000-000000000001",
        "name": "시연용 샘플 업체 (곰팡이·결로)",
        "phone": None,
        "rating": 0.0,
        "review_count": 0,
        "description": None,
        "specialty_work_types": [],
        "chat_available": False,
        "is_sample": True,
    },
    {
        "provider_id": "00000000-0000-4000-8000-000000000002",
        "name": "시연용 샘플 업체 (균열·도장)",
        "phone": None,
        "rating": 0.0,
        "review_count": 0,
        "description": None,
        "specialty_work_types": [],
        "chat_available": False,
        "is_sample": True,
    },
]

router = APIRouter(tags=["providers"], responses={401: _UNAUTHORIZED_RESPONSE})


@router.get(
    "/work-types",
    response_model=list[WorkTypeOut],
    summary="작업 종류 목록 조회",
    description=(
        "업체 검색과 진단의 추천 작업에 사용할 작업 종류 ID와 이름을 반환합니다. "
        "DB에 등록된 작업만 반환하며 클라이언트가 추가·수정할 수 없습니다."
    ),
    response_description="작업 종류 ID와 이름 목록",
)
def list_work_types(owner_id: UUID = Depends(get_current_user)):
    with read_transaction() as conn:
        return conn.execute(
            "SELECT id AS work_type_id, name FROM work_types ORDER BY name, id"
        ).fetchall()


@router.get(
    "/providers",
    response_model=ProviderSearchResponse,
    summary="업체 검색·별점순 추천",
    description=(
        "출장 가능 지역이 일치하는 실제 업체를 별점 내림차순으로 반환합니다.\n\n"
        "- `region_id`는 필수이며 `GET /regions`에서 확인한 UUID여야 합니다. 등록되지 않은 지역은 `422`입니다.\n"
        "- `work_type_id`는 선택입니다. 전달하면 해당 지역과 특화 분야가 모두 일치하는 업체만 반환하고, 생략하면 해당 지역 전체 업체를 반환합니다. 등록되지 않은 작업 종류는 `422`입니다.\n"
        "- 정렬은 `rating DESC, review_count DESC, name ASC, id ASC`입니다.\n"
        "- `chat_available`은 사전 등록된 업체 계정(`providers.account_user_id`)이 연결되어 앱 내 채팅이 가능한지 나타냅니다.\n"
        "- 실제 후보가 하나도 없을 때만 `is_sample=true`와 시연용 샘플 후보를 반환합니다. 샘플 항목은 평점 `0.0`, 리뷰 `0`, 특화 분야 빈 배열, 전화번호 없음입니다.\n"
        "- DB 조회 오류를 빈 목록이나 샘플로 숨기지 않고 `500`으로 반환합니다."
    ),
    response_description="지역·특화 분야에 맞는 업체 후보 목록(별점 내림차순)과 샘플 여부",
    responses={422: _VALIDATION_ERROR_RESPONSE},
)
def list_providers(
    region_id: Annotated[UUID, Query(description="출장 가능 지역 UUID(`GET /regions`).")],
    work_type_id: Annotated[
        UUID | None,
        Query(description="선택 특화 분야 UUID(`GET /work-types`). 생략하면 지역 전체 업체를 조회합니다."),
    ] = None,
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        if conn.execute("SELECT 1 FROM regions WHERE id = %s", (region_id,)).fetchone() is None:
            raise invalid_request("선택한 지역을 찾을 수 없습니다.")
        if (
            work_type_id is not None
            and conn.execute(
                "SELECT 1 FROM work_types WHERE id = %s", (work_type_id,)
            ).fetchone()
            is None
        ):
            raise invalid_request("선택한 작업 종류를 찾을 수 없습니다.")

        params: list[UUID] = [region_id]
        work_type_filter = ""
        if work_type_id is not None:
            work_type_filter = (
                " AND EXISTS ("
                "SELECT 1 FROM provider_work_types AS filter_work "
                "WHERE filter_work.provider_id = p.id AND filter_work.work_type_id = %s)"
            )
            params.append(work_type_id)

        providers = conn.execute(
            f"""
            SELECT
                p.id AS provider_id,
                p.name,
                p.phone,
                p.rating,
                p.review_count,
                p.description,
                (p.account_user_id IS NOT NULL) AS chat_available,
                COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'work_type_id', work_type.id,
                            'name', work_type.name
                        )
                        ORDER BY work_type.name, work_type.id
                    ) FILTER (WHERE work_type.id IS NOT NULL),
                    '[]'::jsonb
                ) AS specialty_work_types
            FROM providers AS p
            JOIN provider_regions AS provider_region
              ON provider_region.provider_id = p.id
             AND provider_region.region_id = %s
            LEFT JOIN provider_work_types AS provider_work
              ON provider_work.provider_id = p.id
            LEFT JOIN work_types AS work_type
              ON work_type.id = provider_work.work_type_id
            WHERE TRUE{work_type_filter}
            GROUP BY p.id
            ORDER BY p.rating DESC, p.review_count DESC, p.name ASC, p.id ASC
            """,
            params,
        ).fetchall()

    if not providers:
        return {"providers": _SAMPLE_PROVIDERS, "is_sample": True}
    return {
        "providers": [{**provider, "is_sample": False} for provider in providers],
        "is_sample": False,
    }


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderDetailOut,
    summary="업체 상세 조회",
    description=(
        "업체의 평점·리뷰 수, 소개, 주소, 영업시간, 경력, 출장 가능 지역, 특화 분야를 반환합니다.\n\n"
        "- 본인 소유와 무관하게 인증된 사용자면 조회할 수 있습니다.\n"
        "- 실제 `providers` 행이 없는 UUID(시연용 샘플 UUID 포함)는 `404`입니다.\n"
        "- 채팅 가능 여부는 `providers.account_user_id` 연결로 판단하며 상세 API는 실제 업체만 반환합니다."
    ),
    response_description="업체 상세 정보와 출장 지역·특화 분야",
    responses={
        404: _PROVIDER_NOT_FOUND_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def get_provider(
    provider_id: Annotated[UUID, Path(description="조회할 업체 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        provider = conn.execute(
            """
            SELECT
                p.id AS provider_id,
                p.name,
                p.phone,
                p.rating,
                p.review_count,
                p.description,
                p.address,
                p.business_hours,
                p.career_years,
                (p.account_user_id IS NOT NULL) AS chat_available,
                COALESCE(
                    (
                        SELECT jsonb_agg(
                            jsonb_build_object(
                                'region_id', region.id,
                                'name', region.name,
                                'display_name', region.display_name
                            )
                            ORDER BY region.display_name, region.id
                        )
                        FROM provider_regions AS provider_region
                        JOIN regions AS region
                          ON region.id = provider_region.region_id
                        WHERE provider_region.provider_id = p.id
                    ),
                    '[]'::jsonb
                ) AS regions,
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
                        WHERE provider_work.provider_id = p.id
                    ),
                    '[]'::jsonb
                ) AS work_types
            FROM providers AS p
            WHERE p.id = %s
            """,
            (provider_id,),
        ).fetchone()
    if provider is None:
        raise not_found("업체를 찾을 수 없습니다.")
    return {**provider, "is_sample": False}
