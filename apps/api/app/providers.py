"""Provider search by service region and work type.

Real candidates come from providers linked to both the requested region and work
type. Sample candidates are returned only when the real search succeeded and
returned nothing; database errors surface as 500 instead of falling back.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.db import read_transaction
from app.errors import invalid_request
from app.schemas import (
    ErrorResponse,
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

# Demo candidates. They never exist in the providers table and carry no real
# contact details, so nothing is invented or mixed into real search results.
_SAMPLE_PROVIDERS = [
    {
        "provider_id": "00000000-0000-4000-8000-000000000001",
        "name": "시연용 샘플 업체 (곰팡이·결로)",
        "phone": None,
        "chat_available": False,
        "is_sample": True,
    },
    {
        "provider_id": "00000000-0000-4000-8000-000000000002",
        "name": "시연용 샘플 업체 (균열·도장)",
        "phone": None,
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
    summary="업체 검색",
    description=(
        "출장 가능 지역과 작업 종류가 **모두** 일치하는 실제 업체를 반환합니다.\n\n"
        "- `region_id`와 `work_type_id`는 `GET /regions`, `GET /work-types`에서 확인한 UUID여야 하며, 등록되지 않은 ID는 `422`입니다.\n"
        "- `chat_available`은 사전 등록된 업체 계정(`providers.account_user_id`)이 연결되어 앱 내 채팅이 가능한지 나타냅니다. "
        "공개 전화번호만 있고 계정이 없는 업체는 `false`입니다.\n"
        "- 실제 후보가 하나도 없을 때만 `is_sample=true`와 시연용 샘플 후보를 반환합니다. 샘플 항목은 `chat_available=false`이며 전화번호가 없습니다.\n"
        "- DB 조회 오류를 빈 목록이나 샘플로 숨기지 않고 `500`으로 반환합니다."
    ),
    response_description="지역·작업이 모두 일치하는 업체 후보 목록과 샘플 여부",
    responses={422: _VALIDATION_ERROR_RESPONSE},
)
def list_providers(
    region_id: Annotated[UUID, Query(description="출장 가능 지역 UUID(`GET /regions`).")],
    work_type_id: Annotated[UUID, Query(description="작업 종류 UUID(`GET /work-types`).")],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        if conn.execute("SELECT 1 FROM regions WHERE id = %s", (region_id,)).fetchone() is None:
            raise invalid_request("선택한 지역을 찾을 수 없습니다.")
        if (
            conn.execute("SELECT 1 FROM work_types WHERE id = %s", (work_type_id,)).fetchone()
            is None
        ):
            raise invalid_request("선택한 작업 종류를 찾을 수 없습니다.")

        providers = conn.execute(
            """
            SELECT
                p.id AS provider_id,
                p.name,
                p.phone,
                (p.account_user_id IS NOT NULL) AS chat_available
            FROM providers p
            JOIN provider_regions pr
              ON pr.provider_id = p.id AND pr.region_id = %s
            JOIN provider_work_types pw
              ON pw.provider_id = p.id AND pw.work_type_id = %s
            ORDER BY p.name, p.id
            """,
            (region_id, work_type_id),
        ).fetchall()

    if not providers:
        return {"providers": _SAMPLE_PROVIDERS, "is_sample": True}
    return {
        "providers": [{**provider, "is_sample": False} for provider in providers],
        "is_sample": False,
    }
