from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Body, Depends

from app.auth import get_current_user
from app.db import read_transaction, transaction
from app.errors import invalid_request, not_found, provider_registration_unavailable
from app.schemas import ErrorResponse, ProfileOut, ProfileUpsertRequest, ProviderRegistrationRequest, RegionOut


def _error_response(
    description: str,
    examples: dict[str, dict],
) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {"application/json": {"examples": examples}},
    }


_UNAUTHORIZED_RESPONSE = _error_response(
    "인증 실패 또는 만료",
    {
        "unauthorized": {
            "summary": "유효하지 않거나 누락된 액세스 토큰",
            "value": {
                "code": "unauthorized",
                "message": "액세스 토큰이 유효하지 않거나 만료되었습니다.",
            },
        }
    },
)

_PROFILE_NOT_FOUND_RESPONSE = _error_response(
    "프로필이 아직 등록되지 않음",
    {
        "profile_not_found": {
            "summary": "프로필 없음",
            "value": {
                "code": "not_found",
                "message": "프로필이 없습니다. 프로필을 먼저 등록해 주세요.",
            },
        }
    },
)

_VALIDATION_ERROR_RESPONSE = _error_response(
    "요청 형식, 지역, 거주 형태 검증 실패",
    {
        "invalid_request": {
            "summary": "필드 또는 지역 검증 실패",
            "value": {
                "code": "invalid_request",
                "message": "요청 형식이 올바르지 않습니다.",
            },
        }
    },
)

router = APIRouter(tags=["profile"], responses={401: _UNAUTHORIZED_RESPONSE})


@router.get(
    "/me/profile",
    response_model=ProfileOut,
    summary="내 프로필 조회",
    description=(
        "검증된 액세스 토큰의 사용자 ID로 본인 프로필만 조회합니다.\n\n"
        "- 프로필이 아직 없으면 `404`를 반환하며, 앱은 프로필 등록 화면으로 이어갑니다.\n"
        "- 이메일·비밀번호는 프로필에 저장하지 않습니다."
    ),
    response_description="본인 닉네임, 역할, 거주 지역, 선택 주소, 거주 형태, 연결된 업체 ID",
    responses={404: _PROFILE_NOT_FOUND_RESPONSE},
)
def get_my_profile(owner_id: UUID = Depends(get_current_user)):
    with read_transaction() as conn:
        profile = conn.execute(
            """
            SELECT
                profile.nickname,
                profile.role,
                profile.region_id,
                profile.address,
                profile.housing_type,
                provider.id AS provider_id
            FROM profiles AS profile
            LEFT JOIN providers AS provider
              ON provider.account_user_id = profile.user_id
            WHERE profile.user_id = %s
            """,
            (owner_id,),
        ).fetchone()
    if profile is None:
        raise not_found("프로필이 없습니다. 프로필을 먼저 등록해 주세요.")
    return profile


@router.put(
    "/me/profile",
    response_model=ProfileOut,
    summary="내 프로필 등록·수정",
    description=(
        "검증된 액세스 토큰의 사용자 ID로 본인 프로필을 최초 등록하거나 수정합니다.\n\n"
        "- `nickname`, `region_id`, `housing_type`은 필수이며 `address`는 선택입니다.\n"
        "- 새 프로필의 역할은 서버가 `requester`로 정합니다. 요청의 `role`/`user_id`/`provider_id` 필드는 허용하지 않습니다. 기존 업체 계정의 `role`은 덮어쓰지 않습니다.\n"
        "- 같은 사용자로 다시 호출하면 기존 프로필을 수정하며, 저장 실패 후 같은 계정으로 재시도할 수 있습니다.\n"
        "- 존재하지 않는 지역과 허용되지 않은 거주 형태는 `422`로 거부합니다."
    ),
    response_description="저장된 본인 프로필",
    responses={422: _VALIDATION_ERROR_RESPONSE},
)
def upsert_my_profile(
    body: Annotated[
        ProfileUpsertRequest,
        Body(
            openapi_examples={
                "requester_profile": {
                    "summary": "요청인 프로필 등록",
                    "value": {
                        "nickname": "하자탐정",
                        "region_id": "550e8400-e29b-41d4-a716-446655440000",
                        "address": "용인시 수지구",
                        "housing_type": "monthly_rent",
                    },
                }
            }
        ),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    nickname = body.nickname.strip()
    address = (body.address or "").strip() or None

    with transaction() as conn:
        region = conn.execute(
            "SELECT 1 FROM regions WHERE id = %s",
            (body.region_id,),
        ).fetchone()
        if region is None:
            raise invalid_request("선택한 지역을 찾을 수 없습니다.")

        profile = conn.execute(
            """
            INSERT INTO profiles
                (user_id, nickname, role, region_id, address, housing_type)
            VALUES (%s, %s, 'requester', %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                nickname = EXCLUDED.nickname,
                region_id = EXCLUDED.region_id,
                address = EXCLUDED.address,
                housing_type = EXCLUDED.housing_type,
                updated_at = now()
            RETURNING nickname, role, region_id, address, housing_type
            """,
            (
                owner_id,
                nickname,
                body.region_id,
                address,
                body.housing_type,
            ),
        ).fetchone()
        provider = conn.execute(
            "SELECT id AS provider_id FROM providers WHERE account_user_id = %s",
            (owner_id,),
        ).fetchone()
    return {
        **profile,
        "provider_id": provider["provider_id"] if provider is not None else None,
    }


@router.post(
    "/me/provider",
    response_model=ProfileOut,
    summary="업체 회원 등록",
    description=(
        "로그인한 사용자를 업체 회원으로 등록합니다. 업체 정보(providers)와 활동 지역을 만들고 프로필 역할을 `provider`로 정합니다.\n\n"
        "- 같은 사용자로 다시 호출하면 업체명·연락처·소개·지역을 갱신합니다.\n"
        "- 업체 회원은 활동 지역의 진행 중 견적 요청서를 모두 받고 업체 제안서를 보낼 수 있습니다.\n"
        "- 서버에 업체 등록 권한(마이그레이션 016)이 적용되지 않았으면 `503`(`provider_registration_unavailable`)입니다."
    ),
    response_description="업체 회원으로 저장된 본인 프로필",
    responses={422: _VALIDATION_ERROR_RESPONSE, 503: {"model": ErrorResponse, "description": "업체 등록 권한 미적용"}},
)
def register_provider(
    body: ProviderRegistrationRequest,
    owner_id: UUID = Depends(get_current_user),
):
    name = body.name.strip()
    phone = body.phone.strip()
    description = (body.description or "").strip() or None
    if not name or not phone:
        raise invalid_request("업체명과 연락처를 입력해 주세요.")

    try:
        with transaction() as conn:
            if conn.execute("SELECT 1 FROM regions WHERE id = %s", (body.region_id,)).fetchone() is None:
                raise invalid_request("선택한 지역을 찾을 수 없습니다.")
            work_type_ids = list(dict.fromkeys(body.work_type_ids))
            if work_type_ids:
                found = conn.execute(
                    "SELECT count(*) AS n FROM work_types WHERE id = ANY(%s)", (work_type_ids,)
                ).fetchone()["n"]
                if found != len(work_type_ids):
                    raise invalid_request("선택한 작업 종류를 찾을 수 없습니다.")

            profile = conn.execute(
                """
                INSERT INTO profiles (user_id, nickname, role, region_id, address, housing_type)
                VALUES (%s, %s, 'provider', %s, NULL, 'other')
                ON CONFLICT (user_id) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    role = 'provider',
                    region_id = EXCLUDED.region_id,
                    updated_at = now()
                RETURNING nickname, role, region_id, address, housing_type
                """,
                (owner_id, name, body.region_id),
            ).fetchone()

            provider = conn.execute(
                "SELECT id FROM providers WHERE account_user_id = %s", (owner_id,)
            ).fetchone()
            if provider is None:
                provider = conn.execute(
                    """
                    INSERT INTO providers (name, phone, description, account_user_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name, phone, description, owner_id),
                ).fetchone()
            else:
                conn.execute(
                    "UPDATE providers SET name = %s, phone = %s, description = %s WHERE id = %s",
                    (name, phone, description, provider["id"]),
                )
                conn.execute("DELETE FROM provider_regions WHERE provider_id = %s", (provider["id"],))
                conn.execute("DELETE FROM provider_work_types WHERE provider_id = %s", (provider["id"],))

            conn.execute(
                "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
                (provider["id"], body.region_id),
            )
            for work_type_id in work_type_ids:
                conn.execute(
                    "INSERT INTO provider_work_types (provider_id, work_type_id) VALUES (%s, %s)",
                    (provider["id"], work_type_id),
                )
    except psycopg.errors.InsufficientPrivilege:
        raise provider_registration_unavailable() from None

    return {**profile, "provider_id": provider["id"]}


@router.get(
    "/regions",
    response_model=list[RegionOut],
    summary="지역 목록 조회",
    description=(
        "프로필의 거주 지역 선택에 사용할 지역 ID와 화면 표시 이름을 반환합니다.\n\n"
        "- 로그인 전 회원가입 화면에서도 쓰도록 인증 없이 조회합니다. 지역 이름은 공개 정보입니다."
    ),
    response_description="지역 ID, 이름, 시·군·구가 포함된 표시 이름 목록",
)
def list_regions():
    with read_transaction() as conn:
        return conn.execute(
            """
            SELECT id AS region_id, name, display_name, parent_id
            FROM regions
            ORDER BY display_name, id
            """
        ).fetchall()
