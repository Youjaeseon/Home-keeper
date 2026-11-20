from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.auth import get_current_user
from app.db import read_transaction
from app.errors import not_found
from app.schemas import (
    ErrorResponse,
    SupportProgramDetail,
    SupportProgramListItem,
)


def _error_response(description: str, examples: dict[str, dict]) -> dict:
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
    "소식지 조회에 필요한 프로필이 아직 등록되지 않음",
    {
        "profile_not_found": {
            "summary": "프로필 없음",
            "value": {
                "code": "not_found",
                "message": "프로필이 없습니다. 거주 지역을 먼저 등록해 주세요.",
            },
        }
    },
)

_PROGRAM_NOT_FOUND_RESPONSE = _error_response(
    "지원 사업을 찾지 못함",
    {
        "program_not_found": {
            "summary": "없는 지원 사업",
            "value": {
                "code": "not_found",
                "message": "지원 사업을 찾을 수 없습니다.",
            },
        }
    },
)

_VALIDATION_ERROR_RESPONSE = _error_response(
    "요청 형식 또는 경로 파라미터 오류",
    {
        "invalid_request": {
            "summary": "요청 스키마 검증 실패",
            "value": {
                "code": "invalid_request",
                "message": "요청 형식이 올바르지 않습니다.",
            },
        }
    },
)

router = APIRouter(
    prefix="/support-programs",
    tags=["support-programs"],
    responses={401: _UNAUTHORIZED_RESPONSE},
)


@router.get(
    "",
    response_model=list[SupportProgramListItem],
    summary="내 지역 주거 지원 사업 목록",
    description=(
        "검증된 액세스 토큰의 사용자 프로필을 기준으로 주거 지원 사업을 조회합니다.\n\n"
        "- 프로필의 거주 지역, 그 상위 지역의 공고, 전국 공고를 함께 반환합니다.\n"
        "- 다른 지역의 공고는 반환하지 않습니다.\n"
        "- 진행 중 공고를 먼저, 그중 거주 형태 태그가 일치하는 공고를 먼저 정렬하고, "
        "마감된 확정 날짜 공고는 하단에 배치합니다.\n"
        "- `deadline_kind`로 확정 날짜(`fixed`), 공식 상시·연중(`always_open`), "
        "기한 미확인·모호함(`unknown`)을 구분합니다. 마감 공고도 상세에서 확인할 수 있습니다.\n"
        "- 거주 형태 태그 일치(`housing_type_matched`)는 참고 표시일 뿐 신청 자격을 확정하지 않습니다.\n"
        "- 프로필이 없으면 `404`를 반환합니다. DB 오류를 빈 목록으로 숨기지 않습니다."
    ),
    response_description="내 지역·상위 지역·전국 주거 지원 사업 목록",
    responses={404: _PROFILE_NOT_FOUND_RESPONSE, 422: _VALIDATION_ERROR_RESPONSE},
)
def list_support_programs(
    status: Annotated[
        Literal["all", "active"],
        Query(description="`all`은 마감 공고 포함, `active`는 마감되지 않은 공고만 조회."),
    ] = "all",
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        profile = conn.execute(
            "SELECT region_id, housing_type FROM profiles WHERE user_id = %s",
            (owner_id,),
        ).fetchone()
        if profile is None:
            raise not_found("프로필이 없습니다. 거주 지역을 먼저 등록해 주세요.")

        return conn.execute(
            """
            WITH RECURSIVE ancestor_regions AS (
                SELECT id, parent_id
                FROM regions
                WHERE id = %s
                UNION ALL
                SELECT parent.id, parent.parent_id
                FROM regions AS parent
                JOIN ancestor_regions AS child ON parent.id = child.parent_id
            ),
            visible AS (
                SELECT
                    program.id,
                    program.title,
                    program.summary,
                    program.organization_name,
                    program.region_scope,
                    program.target_housing_types,
                    program.deadline_text,
                    program.deadline_date,
                    program.deadline_kind,
                    program.detail_url,
                    program.source,
                    program.source_attribution,
                    program.source_checked_at,
                    program.updated_at,
                    CASE
                        WHEN program.region_scope = 'national' THEN '전국'
                        ELSE region.display_name
                    END AS region_name,
                    (
                        program.deadline_kind = 'fixed'
                        AND program.deadline_date
                            < ((now() AT TIME ZONE 'Asia/Seoul')::date)
                    ) AS is_closed,
                    (%s::text = ANY (program.target_housing_types)) AS housing_type_matched
                FROM support_programs AS program
                LEFT JOIN regions AS region ON region.id = program.region_id
                WHERE (program.region_scope = 'national'
                   OR program.region_id IN (SELECT id FROM ancestor_regions))
                  AND NOT (
                      program.source = 'gov24_api'
                      AND EXISTS (
                          SELECT 1
                          FROM support_programs AS seed_program
                          WHERE seed_program.source = 'seed'
                            AND seed_program.organization_name = program.organization_name
                            AND seed_program.region_scope = program.region_scope
                            AND seed_program.region_id IS NOT DISTINCT FROM program.region_id
                            AND lower(
                                regexp_replace(
                                    regexp_replace(seed_program.title, '사업$', ''),
                                    '\s+', '', 'g'
                                )
                            ) = lower(
                                regexp_replace(
                                    regexp_replace(program.title, '사업$', ''),
                                    '\s+', '', 'g'
                                )
                            )
                      )
                  )
            )
            SELECT *
            FROM visible
            WHERE (%s = 'all' OR is_closed = false)
            ORDER BY
                is_closed ASC,
                housing_type_matched DESC,
                CASE WHEN deadline_kind = 'fixed' THEN deadline_date END ASC NULLS LAST,
                source_checked_at DESC,
                title ASC,
                id ASC
            """,
            (profile["region_id"], profile["housing_type"], status),
        ).fetchall()


@router.get(
    "/{program_id}",
    response_model=SupportProgramDetail,
    summary="주거 지원 사업 상세",
    description=(
        "지원 사업의 공식 원문 요약, 지원 대상·내용, 신청 방법, 신청기한, "
        "공식 원문 URL과 출처·확인 시점을 반환합니다.\n\n"
        "- 지원 사업은 공공 정보이므로 프로필 없이도 인증된 사용자가 조회할 수 있습니다.\n"
        "- 존재하지 않는 사업은 `404`를 반환합니다.\n"
        "- `deadline_date`가 없어도 `deadline_text`와 `deadline_kind`로 기한 불명을 구분합니다."
    ),
    response_description="지원 사업 상세 요약과 공식 출처 정보",
    responses={404: _PROGRAM_NOT_FOUND_RESPONSE, 422: _VALIDATION_ERROR_RESPONSE},
)
def get_support_program(
    program_id: Annotated[UUID, Path(description="조회할 주거 지원 사업의 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        program = conn.execute(
            """
            SELECT
                program.id,
                program.title,
                program.summary,
                program.organization_name,
                program.region_scope,
                program.target_housing_types,
                program.support_target,
                program.support_content,
                program.selection_criteria,
                program.apply_method,
                program.deadline_text,
                program.deadline_date,
                program.deadline_kind,
                program.detail_url,
                program.source,
                program.source_attribution,
                program.source_checked_at,
                program.synced_at,
                program.updated_at,
                CASE
                    WHEN program.region_scope = 'national' THEN '전국'
                    ELSE region.display_name
                END AS region_name,
                (
                    program.deadline_kind = 'fixed'
                    AND program.deadline_date
                        < ((now() AT TIME ZONE 'Asia/Seoul')::date)
                ) AS is_closed
            FROM support_programs AS program
            LEFT JOIN regions AS region ON region.id = program.region_id
            WHERE program.id = %s
            """,
            (program_id,),
        ).fetchone()
    if program is None:
        raise not_found("지원 사업을 찾을 수 없습니다.")
    return program
