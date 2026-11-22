"""Landlord inspection and provider quote request drafts.

Templates are built on the server without a model call. Draft text comes from a
single configured LLM provider; nothing is stored when the call fails, and stale
results are never saved over a newer input revision or diagnosis generation.
"""

import re
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app import llm
from app.auth import get_current_user
from app.db import read_transaction, transaction
from app.errors import (
    llm_quota_exceeded,
    ApiError,
    diagnosis_conflict,
    llm_failed,
    llm_timeout,
    llm_unavailable,
    not_found,
    revision_conflict,
)
from app.schemas import (
    ConflictErrorResponse,
    DraftResponse,
    DraftTemplateResponse,
    ErrorResponse,
)

DraftKind = Literal["landlord", "provider"]

_DRAFT_COLUMNS = {
    "landlord": (
        "landlord_draft",
        "landlord_draft_revision",
        "landlord_draft_diagnosis_generation",
    ),
    "provider": (
        "provider_draft",
        "provider_draft_revision",
        "provider_draft_diagnosis_generation",
    ),
}

_TITLES = {
    "landlord": "임대인·관리실 점검 요청",
    "provider": "수리 업체 견적 요청",
}

_REQUEST_LINES = {
    "landlord": [
        "위 하자의 원인 점검과 처리 방법을 안내해 주세요.",
        "방문 점검이 필요하면 가능한 일정을 알려 주세요.",
    ],
    "provider": [
        "현장 확인 후 작업 범위와 견적을 안내해 주세요.",
        "가능한 방문 일정도 함께 알려 주세요.",
    ],
}

# Profile fields (nickname, address, housing type) are never read here, and
# free-form record text is scrubbed of obvious contact details before any
# external model call.
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_REDACTED = "[개인정보 제거]"


def _redact(value: str) -> str:
    return _PHONE_PATTERN.sub(_REDACTED, _EMAIL_PATTERN.sub(_REDACTED, value))


def _error_response(
    model: type[ErrorResponse],
    description: str,
    examples: dict[str, dict],
) -> dict:
    return {
        "model": model,
        "description": description,
        "content": {"application/json": {"examples": examples}},
    }


_UNAUTHORIZED_RESPONSE = _error_response(
    ErrorResponse,
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

_RECORD_NOT_FOUND_RESPONSE = _error_response(
    ErrorResponse,
    "기록을 찾을 수 없거나 다른 사용자의 기록임",
    {
        "record_not_found": {
            "summary": "기록 없음 또는 접근 권한 없음",
            "value": {"code": "not_found", "message": "기록을 찾을 수 없습니다."},
        }
    },
)

_VALIDATION_ERROR_RESPONSE = _error_response(
    ErrorResponse,
    "요청 형식 또는 요청문 종류 오류",
    {
        "invalid_request": {
            "summary": "`kind`는 `landlord` 또는 `provider`만 허용",
            "value": {
                "code": "invalid_request",
                "message": "요청 형식이 올바르지 않습니다.",
            },
        }
    },
)

_DRAFT_CONFLICT_RESPONSE = _error_response(
    ConflictErrorResponse,
    "입력·진단 버전 충돌 또는 진단 없음",
    {
        "revision_conflict": {
            "summary": "생성 중 입력 변경",
            "value": {
                "code": "revision_conflict",
                "message": "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
                "input_revision": 2,
            },
        },
        "diagnosis_conflict": {
            "summary": "생성 중 진단 교체",
            "value": {
                "code": "diagnosis_conflict",
                "message": "진단이 교체되어 요청문을 저장하지 않았습니다. 다시 생성해 주세요.",
                "input_revision": 1,
            },
        },
        "diagnosis_required": {
            "summary": "진단 결과 없음",
            "value": {
                "code": "diagnosis_required",
                "message": "진단 결과가 없어 요청문을 생성할 수 없습니다. 먼저 분석을 완료하거나 기본 양식을 사용해 주세요.",
                "input_revision": 0,
            },
        },
    },
)

_LLM_ERROR_RESPONSE = _error_response(
    ErrorResponse,
    "외부 모델 호출 실패·제한 시간 초과·키 미설정",
    {
        "llm_error": {
            "summary": "모델 호출 또는 응답 형식 오류",
            "value": {
                "code": "llm_error",
                "message": "요청문 생성에 실패했습니다. 다시 시도하거나 기본 양식을 사용해 주세요.",
            },
        },
        "llm_timeout": {
            "summary": "모델 응답 제한 시간 초과",
            "value": {
                "code": "llm_timeout",
                "message": "요청문 생성 응답이 지연되고 있습니다. 다시 시도하거나 기본 양식을 사용해 주세요.",
            },
        },
        "llm_unavailable": {
            "summary": "모델 키 미설정",
            "value": {
                "code": "llm_unavailable",
                "message": "요청문 생성 모델이 설정되지 않았습니다. 기본 양식을 사용해 주세요.",
            },
        },
    },
)

_LLM_FAILURE_RESPONSES = {
    502: _LLM_ERROR_RESPONSE,
    503: _LLM_ERROR_RESPONSE,
    504: _LLM_ERROR_RESPONSE,
}

router = APIRouter(
    prefix="/records",
    tags=["drafts"],
    responses={401: _UNAUTHORIZED_RESPONSE},
)


def _diagnosis_facts(diagnosis: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(diagnosis, dict):
        return None
    suspected = diagnosis.get("suspected_types")
    causes = diagnosis.get("causes")
    unknowns = diagnosis.get("unknowns")
    score = diagnosis.get("severity_score")
    return {
        "suspected_types": [str(item) for item in suspected] if isinstance(suspected, list) else [],
        "causes": [str(item) for item in causes] if isinstance(causes, list) else [],
        "unknowns": [str(item) for item in unknowns] if isinstance(unknowns, list) else [],
        "severity": f"{score}% ({diagnosis.get('severity_level')})"
        if isinstance(score, int)
        else "판단 보류",
        "source": str(diagnosis.get("source") or "unknown"),
    }


def _record_lines(record: dict) -> list[str]:
    return [
        f"- 위치: {record['location'] or '미입력'}",
        f"- 재질: {record['material'] or '미입력'}",
        f"- 증상 메모: {record['symptoms'] or '미입력'}",
    ]


def build_template(kind: DraftKind, record: dict) -> str:
    lines = [
        f"안녕하세요. 아래 하자에 대한 {_TITLES[kind]}을 드립니다.",
        "",
        "[확인된 내용]",
        *_record_lines(record),
    ]

    facts = _diagnosis_facts(record["diagnosis"])
    if facts is None:
        lines += ["", "[진단]", "- 아직 진단 결과가 없습니다. 확인된 내용만 정리했습니다."]
    else:
        lines += ["", "[진단 참고(추정)]"]
        lines.append(f"- 의심 유형: {', '.join(facts['suspected_types']) or '미확인'}")
        lines.append(f"- 심각도: {facts['severity']} (참고용)")
        lines.append(
            f"- 추정 원인(확인 필요): {'; '.join(facts['causes']) or '미확인'}"
        )
        lines.append(
            f"- 추가 확인이 필요한 사항: {'; '.join(facts['unknowns']) or '없음'}"
        )

    lines += ["", "[요청 사항]", *[f"- {line}" for line in _REQUEST_LINES[kind]], "", "감사합니다."]
    return "\n".join(lines)


# 임대인 문자: 분석 보고서가 아니라 세입자가 그대로 보낼 수 있는 정중한 요청 문자 (Hyeok 결정, 법 조항 인용 없음)
LANDLORD_SYSTEM_PROMPT = """\
너는 세입자가 집주인(임대인)에게 보낼 정중한 하자 수리 요청 문자를 써 주는 도우미다.
- 그대로 보낼 수 있는 문자 한 통만 쓴다. 제목·번호 목록·마크다운·이모지 없이 5~7문장, 300자 안팎.
- 순서: 인사와 '○○호 세입자입니다' → 발견 시기('○월 ○일쯤')와 위치·상태 한두 문장, '사진 첨부드립니다' → 불편이나 악화 우려 한 문장 → 점검·수리 요청과 방문 가능한 날짜 문의 → '편하실 때 회신 부탁드립니다'와 감사 인사.
- 원인은 '결로나 누수가 의심됩니다'처럼 짧게만 쓰고 단정하지 않는다. 심각도 %, 분석·모델 용어, 원인 목록은 쓰지 않는다.
- 법 조항이나 책임을 따지는 표현, 기한을 강요하는 표현 없이 정중하게 요청만 한다.
- 이름·주소·연락처·날짜는 만들지 않고 '○○호', '○월 ○일'처럼 빈칸으로 둔다.
- 문자 본문만 출력한다.
"""


def build_landlord_prompt(record: dict) -> str:
    facts = _diagnosis_facts(record["diagnosis"])
    lines = [
        "아래 하자 내용으로 집주인에게 보낼 문자를 써 주세요.",
        *[_redact(line) for line in _record_lines(record)],
    ]
    if facts is not None:
        lines.append(f"- 하자 유형: {', '.join(facts['suspected_types']) or '미확인'}")
        lines.append(f"- 의심 원인(참고): {'; '.join(facts['causes'][:2]) or '미확인'}")
    return "\n".join(lines)


def build_prompt(kind: DraftKind, record: dict) -> str:
    facts = _diagnosis_facts(record["diagnosis"])
    lines = [
        f"다음 하자 기록으로 {_TITLES[kind]} 요청문 초안을 작성해 주세요.",
        "",
        "[사용자 입력(확인된 사실)]",
        *[_redact(line) for line in _record_lines(record)],
        "",
        "[서버 진단 결과(추정, 단정 금지)]",
    ]
    if facts is None:
        lines.append("- 진단 결과 없음")
    else:
        lines.append(f"- 의심 유형: {', '.join(facts['suspected_types']) or '미확인'}")
        lines.append(f"- 심각도: {facts['severity']}")
        lines.append(f"- 추정 원인: {'; '.join(facts['causes']) or '미확인'}")
        lines.append(
            f"- 추가 확인이 필요한 사항: {'; '.join(facts['unknowns']) or '없음'}"
        )
        lines.append(f"- 진단 결과 출처: {facts['source']}")
    lines += [
        "",
        "구성: 1) 확인된 내용 2) 추정 원인(확인 필요) 3) 추가 확인이 필요한 사항 4) 요청 사항.",
    ]
    return "\n".join(lines)


def _stored_draft(
    kind: DraftKind,
    record: dict,
    revision: int,
    generation: int,
) -> dict | None:
    text_column, revision_column, generation_column = _DRAFT_COLUMNS[kind]
    text = record[text_column]
    if (
        text is None
        or record[revision_column] != revision
        or record[generation_column] != generation
    ):
        return None
    return {
        "kind": kind,
        "text": text,
        "input_revision": revision,
        "diagnosis_generation": generation,
    }


@router.post(
    "/{record_id}/drafts/{kind}",
    response_model=DraftResponse,
    summary="점검·견적 요청문 생성",
    description=(
        "저장된 입력과 진단으로 임대인 점검 요청문(`landlord`) 또는 업체 견적 요청문(`provider`)을 생성합니다.\n\n"
        "- 입력 버전과 진단 생성 번호가 모두 일치하는 기존 요청문은 모델을 호출하지 않고 재사용합니다. "
        "`regenerate=true`를 보내면 새로 생성해 최신본을 교체합니다.\n"
        "- 진단 결과가 없으면 `409`(`diagnosis_required`)이며, 기본 양식 API는 계속 사용할 수 있습니다.\n"
        "- 생성 중 입력이 바뀌면 `409`(`revision_conflict`), 진단이 교체되면 `409`(`diagnosis_conflict`)를 반환하고 아무것도 저장하지 않습니다.\n"
        "- 모델 키 미설정은 `503`, 호출·응답 형식 오류는 `502`, 제한 시간 초과는 `504`입니다. 실패해도 기존 요청문은 유지됩니다.\n"
        "- 외부 모델에는 기록의 위치·재질·증상과 진단 결과만 전송하며, 프로필 닉네임·주소·거주 형태는 전송하지 않습니다. "
        "증상 메모의 이메일·휴대전화 번호는 전송 전에 제거합니다. 프롬프트·응답·요청 본문은 로그에 남기지 않습니다."
    ),
    response_description="생성 또는 재사용된 요청문과 생성에 사용한 입력 버전·진단 생성 번호",
    responses={
        404: _RECORD_NOT_FOUND_RESPONSE,
        409: _DRAFT_CONFLICT_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
        **_LLM_FAILURE_RESPONSES,
    },
)
def create_draft(
    record_id: Annotated[UUID, Path(description="요청문을 만들 하자 기록의 UUID.")],
    kind: Annotated[
        DraftKind,
        Path(description="요청문 종류. `landlord`(임대인 점검) 또는 `provider`(업체 견적)입니다."),
    ],
    regenerate: Annotated[
        bool,
        Query(description="`true`면 기존 요청문을 재사용하지 않고 모델로 새로 생성합니다."),
    ] = False,
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
            (record_id, owner_id),
        ).fetchone()
        if record is None:
            raise not_found()

        revision = record["input_revision"]
        generation = record["diagnosis_generation"]

        if not regenerate:
            stored = _stored_draft(kind, record, revision, generation)
            if stored is not None:
                return stored

        if record["diagnosis"] is None:
            raise ApiError(
                409,
                "diagnosis_required",
                "진단 결과가 없어 요청문을 생성할 수 없습니다. 먼저 분석을 완료하거나 기본 양식을 사용해 주세요.",
                input_revision=revision,
            )
        prompt = build_landlord_prompt(record) if kind == "landlord" else build_prompt(kind, record)
    # No row lock is held during the external call; versions are re-checked below.

    try:
        text = llm.generate_text(
            prompt, system_prompt=LANDLORD_SYSTEM_PROMPT if kind == "landlord" else None
        )
    except llm.LlmUnavailable:
        raise llm_unavailable() from None
    except llm.LlmQuotaExceeded:
        raise llm_quota_exceeded() from None
    except llm.LlmTimeout:
        raise llm_timeout() from None
    except llm.LlmError:
        raise llm_failed() from None

    with transaction() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
            (record_id, owner_id),
        ).fetchone()
        if record is None:
            raise not_found()
        if record["input_revision"] != revision:
            raise revision_conflict(record["input_revision"])
        if record["diagnosis"] is None or record["diagnosis_generation"] != generation:
            raise diagnosis_conflict(record["input_revision"])

        if not regenerate:
            stored = _stored_draft(kind, record, revision, generation)
            if stored is not None:
                return stored

        text_column, revision_column, generation_column = _DRAFT_COLUMNS[kind]
        conn.execute(
            f"""
            UPDATE records
            SET {text_column} = %s,
                {revision_column} = %s,
                {generation_column} = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (text, revision, generation, record_id),
        )

    return {
        "kind": kind,
        "text": text,
        "input_revision": revision,
        "diagnosis_generation": generation,
    }


@router.get(
    "/{record_id}/drafts/{kind}/template",
    response_model=DraftTemplateResponse,
    summary="점검·견적 요청문 기본 양식 조회",
    description=(
        "모델을 호출하지 않고 현재 기록의 확인된 사실(위치·재질·증상)과 진단 참고 내용을 채운 기본 양식을 반환합니다.\n\n"
        "- 진단이 아직 없거나 요청문 생성에 실패한 경우에도 사용할 수 있습니다. 이때 `diagnosis_generation`은 `null`입니다.\n"
        "- 기본 양식은 저장되지 않으며, 앱에서 자유롭게 편집해 사용합니다. 편집본 저장 API는 없습니다.\n"
        "- 본인 소유 기록만 조회할 수 있습니다."
    ),
    response_description="현재 기록을 채운 요청문 기본 양식",
    responses={404: _RECORD_NOT_FOUND_RESPONSE, 422: _VALIDATION_ERROR_RESPONSE},
)
def get_draft_template(
    record_id: Annotated[UUID, Path(description="기본 양식을 만들 하자 기록의 UUID.")],
    kind: Annotated[
        DraftKind,
        Path(description="요청문 종류. `landlord`(임대인 점검) 또는 `provider`(업체 견적)입니다."),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s",
            (record_id, owner_id),
        ).fetchone()
    if record is None:
        raise not_found()
    return {
        "kind": kind,
        "text": build_template(kind, record),
        "input_revision": record["input_revision"],
        "diagnosis_generation": (
            record["diagnosis_generation"] if record["diagnosis"] is not None else None
        ),
    }
