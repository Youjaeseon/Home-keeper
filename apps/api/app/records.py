from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, Path, UploadFile
from psycopg.types.json import Jsonb

from app.auth import get_current_user
from app.config import get_settings
from app.db import read_transaction, transaction
from app import diagnosis, llm, storage
from app.errors import (
    llm_quota_exceeded,
    diagnosis_llm_failed,
    diagnosis_llm_timeout,
    diagnosis_llm_unavailable,
    invalid_request,
    message_conflict,
    not_found,
    revision_conflict,
)
from app.sample_analysis import (
    MAX_PHOTO_BYTES,
    PHOTO_ROLES,
    build_sample_analysis,
)
from app.sample_questions import SOURCE, build_sample_decision
from app.vision import analyze_photos
from app.schemas import (
    AnalyzeResponse,
    ConflictErrorResponse,
    ErrorResponse,
    MessageCreateRequest,
    MessageSaveResponse,
    MessageUpdateRequest,
    NextQuestionResponse,
    RecordCreateResponse,
    RecordListItem,
    RecordOut,
    RecordPatchRequest,
    RecordPatchResponse,
)


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
            "value": {
                "code": "not_found",
                "message": "기록을 찾을 수 없습니다.",
            },
        }
    },
)

_VALIDATION_ERROR_RESPONSE = _error_response(
    ErrorResponse,
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

_MESSAGE_POST_NOT_FOUND_RESPONSE = _error_response(
    ErrorResponse,
    "기록 또는 질문을 찾을 수 없음",
    {
        "record_not_found": {
            "summary": "기록 없음 또는 다른 사용자의 기록",
            "value": {
                "code": "not_found",
                "message": "기록을 찾을 수 없습니다.",
            },
        },
        "question_not_found": {
            "summary": "해당 기록에 존재하지 않는 질문",
            "value": {
                "code": "not_found",
                "message": "질문을 찾을 수 없어요.",
            },
        },
    },
)

_MESSAGE_POST_CONFLICT_RESPONSE = _error_response(
    ConflictErrorResponse,
    "입력 버전 충돌 또는 동일 client_message_id 내용 충돌",
    {
        "revision_conflict": {
            "summary": "입력 버전 충돌",
            "value": {
                "code": "revision_conflict",
                "message": "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
                "input_revision": 2,
            },
        },
        "message_conflict": {
            "summary": "동일 client_message_id 내용 충돌",
            "value": {
                "code": "message_conflict",
                "message": "같은 메시지 ID로 다른 내용이 이미 저장되었습니다.",
                "input_revision": 1,
            },
        },
    },
)

_MESSAGE_POST_VALIDATION_ERROR_RESPONSE = _error_response(
    ErrorResponse,
    "요청 형식 오류 또는 질문에 없는 선택지",
    {
        "invalid_request": {
            "summary": "요청 스키마 또는 답변 규칙 검증 실패",
            "value": {
                "code": "invalid_request",
                "message": "요청 형식이 올바르지 않습니다.",
            },
        },
        "unknown_option": {
            "summary": "질문에 속하지 않는 선택지 ID",
            "value": {
                "code": "invalid_request",
                "message": "해당 질문의 선택지를 찾을 수 없어요.",
            },
        },
    },
)

_MESSAGE_PUT_NOT_FOUND_RESPONSE = _error_response(
    ErrorResponse,
    "기록 또는 수정 가능한 사용자 메시지를 찾을 수 없음",
    {
        "record_not_found": {
            "summary": "기록 없음 또는 다른 사용자의 기록",
            "value": {
                "code": "not_found",
                "message": "기록을 찾을 수 없습니다.",
            },
        },
        "message_not_found": {
            "summary": "메시지 없음 또는 assistant 메시지 수정 시도",
            "value": {
                "code": "not_found",
                "message": "메시지를 찾을 수 없어요.",
            },
        },
    },
)

_MESSAGE_PUT_CONFLICT_RESPONSE = _error_response(
    ConflictErrorResponse,
    "입력 버전 충돌",
    {
        "revision_conflict": {
            "summary": "편집 시작 시점과 서버 최신 버전 불일치",
            "value": {
                "code": "revision_conflict",
                "message": "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
                "input_revision": 2,
            },
        }
    },
)

_NEXT_QUESTION_CONFLICT_RESPONSE = _error_response(
    ConflictErrorResponse,
    "질문 생성 중 기록 입력 버전이 변경됨",
    {
        "revision_conflict": {
            "summary": "입력 변경으로 생성 결과를 저장하지 않음",
            "value": {
                "code": "revision_conflict",
                "message": "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
                "input_revision": 2,
            },
        }
    },
)

_ANALYZE_CONFLICT_RESPONSE = _error_response(
    ConflictErrorResponse,
    "분석 중 기록 입력 버전이 변경됨",
    {
        "revision_conflict": {
            "summary": "입력 변경으로 분석 결과를 저장하지 않음",
            "value": {
                "code": "revision_conflict",
                "message": "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
                "input_revision": 2,
            },
        }
    },
)

router = APIRouter(
    prefix="/records",
    tags=["records"],
    responses={401: _UNAUTHORIZED_RESPONSE},
)

_MESSAGE_COLUMNS = """
    id, record_id, question_id, sequence, sender, content,
    client_message_id, input_revision, created_at
"""


def _lock_record(conn, record_id: UUID, owner_id: UUID) -> dict:
    record = conn.execute(
        "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
        (record_id, owner_id),
    ).fetchone()
    if record is None:
        raise not_found()
    return record


def _get_record(conn, record_id: UUID, owner_id: UUID) -> dict:
    record = conn.execute(
        """
        SELECT record.*, region.display_name AS region_name
        FROM records AS record
        LEFT JOIN regions AS region ON region.id = record.region_id
        WHERE record.id = %s AND record.owner_id = %s
        """,
        (record_id, owner_id),
    ).fetchone()
    if record is None:
        raise not_found()
    return record


def _validate_region(conn, region_id: UUID | None) -> None:
    if region_id is None:
        return
    if conn.execute("SELECT 1 FROM regions WHERE id = %s", (region_id,)).fetchone() is None:
        raise invalid_request("선택한 지역을 찾을 수 없습니다.")


def _answer_content(conn, record_id: UUID, body: MessageCreateRequest) -> str:
    options = None
    if body.question_id is not None:
        question = conn.execute(
            "SELECT options FROM questions WHERE id = %s AND record_id = %s",
            (body.question_id, record_id),
        ).fetchone()
        if question is None:
            raise not_found("질문을 찾을 수 없어요.")
        options = question["options"]

    if body.content is not None:
        return body.content

    option = next(
        (
            item
            for item in (options or [])
            if isinstance(item, dict) and item.get("id") == body.selected_option_id
        ),
        None,
    )
    if option is None or not isinstance(option.get("label"), str):
        raise invalid_request("해당 질문의 선택지를 찾을 수 없어요.")
    return option["label"]


def _draft_out(
    text: str | None,
    revision: int | None,
    generation: int | None,
    current_revision: int,
    current_generation: int,
) -> dict | None:
    if text is None:
        return None
    return {
        "text": text,
        "input_revision": revision,
        "diagnosis_generation": generation,
        "is_current": revision == current_revision and generation == current_generation,
    }


def _current_next_question_result(record: dict) -> dict | None:
    if (
        record["next_question_result"] is not None
        and record["next_question_revision"] == record["input_revision"]
    ):
        return record["next_question_result"]
    return None


def _load_next_question_state(conn, record_id: UUID) -> dict:
    questions = conn.execute(
        """
        SELECT id, sequence, content, options, answered
        FROM questions WHERE record_id = %s ORDER BY sequence
        """,
        (record_id,),
    ).fetchall()
    messages = conn.execute(
        """
        SELECT id, question_id, sequence, sender, content
        FROM messages WHERE record_id = %s ORDER BY sequence
        """,
        (record_id,),
    ).fetchall()
    return {"questions": questions, "messages": messages}


def _allocate_conversation_sequence(conn, record_id: UUID) -> int:
    allocated = conn.execute(
        """
        UPDATE records
        SET conversation_sequence = conversation_sequence + 1,
            updated_at = now()
        WHERE id = %s
        RETURNING conversation_sequence
        """,
        (record_id,),
    ).fetchone()
    return allocated["conversation_sequence"]


def _supported_photo_header(head: bytes) -> bool:
    if head.startswith(b"\xff\xd8\xff"):
        return True
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    return (
        len(head) >= 12
        and head[4:8] == b"ftyp"
        and head[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}
    )


def _validate_photo(upload: UploadFile) -> None:
    head = upload.file.read(16)
    if not head or not _supported_photo_header(head):
        raise invalid_request("사진은 JPEG, PNG, HEIC/HEIF 형식만 업로드할 수 있습니다.")

    total = len(head)
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_PHOTO_BYTES:
            raise invalid_request("사진 한 장은 10MB 이하여야 합니다.")


def _validate_photo_roles(photo_roles: list[str], photo_count: int) -> None:
    if len(photo_roles) != photo_count:
        raise invalid_request("사진 수와 photo_roles 수가 일치해야 합니다.")
    if any(role not in PHOTO_ROLES for role in photo_roles):
        raise invalid_request("photo_roles는 overview 또는 closeup이어야 합니다.")
    if len(set(photo_roles)) != len(photo_roles):
        raise invalid_request("사진 역할은 서로 달라야 합니다.")



@router.post(
    "",
    response_model=RecordCreateResponse,
    status_code=201,
    summary="하자 기록 생성",
    description=(
        "로그인한 사용자(`sub`)를 소유자로 새 하자 기록을 생성합니다.\n\n"
        "- 요청 본문은 필요하지 않습니다.\n"
        "- 생성된 기록의 초기 `input_revision`은 `0`입니다."
    ),
    response_description="생성된 하자 기록 ID와 초기 입력 버전(0)",
)
def create_record(owner_id: UUID = Depends(get_current_user)):
    with transaction() as conn:
        record = conn.execute(
            "INSERT INTO records (owner_id) VALUES (%s) RETURNING id, input_revision",
            (owner_id,),
        ).fetchone()
    return {"record_id": record["id"], "input_revision": record["input_revision"]}


@router.get(
    "",
    response_model=list[RecordListItem],
    summary="내 하자 기록 목록",
    description=(
        "검증된 액세스 토큰의 사용자 ID로 본인 소유의 하자 기록을 최근 수정 순으로 조회합니다.\n\n"
        "- 전체 진단·대화 내용은 포함하지 않고, 목록 화면에 필요한 위치·증상·의심 유형·심각도만 요약합니다.\n"
        "- 진단이 아직 없으면 `suspected_types`는 빈 배열, `severity_score`와 `severity_level`은 `null`입니다.\n"
        "- 다른 사용자의 기록은 결과에 포함하지 않습니다."
    ),
    response_description="최근 수정 순으로 정렬된 내 하자 기록 요약 목록",
)
def list_records(owner_id: UUID = Depends(get_current_user)):
    with read_transaction() as conn:
        return conn.execute(
            """
            SELECT
                record.id AS record_id,
                record.location,
                record.material,
                record.symptoms,
                record.region_id,
                region.display_name AS region_name,
                CASE
                    WHEN jsonb_typeof(record.diagnosis -> 'suspected_types') = 'array'
                    THEN record.diagnosis -> 'suspected_types'
                    ELSE '[]'::jsonb
                END AS suspected_types,
                CASE
                    WHEN jsonb_typeof(record.diagnosis -> 'severity_score') = 'number'
                    THEN (record.diagnosis ->> 'severity_score')::int
                END AS severity_score,
                record.diagnosis ->> 'severity_level' AS severity_level,
                record.created_at,
                record.updated_at
            FROM records AS record
            LEFT JOIN regions AS region ON region.id = record.region_id
            WHERE record.owner_id = %s
            ORDER BY record.updated_at DESC, record.created_at DESC, record.id DESC
            """,
            (owner_id,),
        ).fetchall()


@router.get(
    "/{record_id}",
    response_model=RecordOut,
    summary="하자 기록 상세 조회",
    description=(
        "`REPEATABLE READ` 스냅샷으로 입력(`location`, `material`, `symptoms`, `photo_observations`), "
        "`questions`, `messages`, 최신 생성 결과(`next_question`, `diagnosis`, `drafts`)를 조회합니다.\n\n"
        "- 본인 소유의 하자 기록만 조회할 수 있으며, 다른 사용자 기록이나 없는 기록은 `404`를 반환합니다.\n"
        "- `questions`와 `messages`는 기록 내 공용 `sequence` 오름차순으로 반환되므로, 두 배열을 합쳐 `sequence` 순으로 정렬하면 전체 대화 순서가 유지됩니다.\n"
        "- 생성 결과(`next_question`, `diagnosis`, `drafts`)에는 생성 당시 버전과 `is_current`가 포함되며, 후속 AI 기능 구현 전에는 `null`일 수 있습니다."
    ),
    response_description="하자 기록 상세 정보",
    responses={
        404: _RECORD_NOT_FOUND_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def get_record(
    record_id: Annotated[UUID, Path(description="조회할 하자 기록의 UUID.")],
    owner_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        record = _get_record(conn, record_id, owner_id)
        questions = conn.execute(
            """
            SELECT id, record_id, sequence, content, options, answered,
                   input_revision, created_at
            FROM questions WHERE record_id = %s ORDER BY sequence
            """,
            (record_id,),
        ).fetchall()
        messages = conn.execute(
            f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE record_id = %s ORDER BY sequence",
            (record_id,),
        ).fetchall()

        current_revision = record["input_revision"]
        current_generation = record["diagnosis_generation"]

        next_question = None
        if record["next_question_result"] is not None:
            next_question = {
                "result": record["next_question_result"],
                "input_revision": record["next_question_revision"],
                "is_current": record["next_question_revision"] == current_revision,
            }

        diagnosis = None
        if record["diagnosis"] is not None:
            diagnosis = {
                "diagnosis": record["diagnosis"],
                "input_revision": record["diagnosis_revision"],
                "generation": current_generation,
                "is_current": record["diagnosis_revision"] == current_revision,
            }

        return {
            "record_id": record["id"],
            "location": record["location"],
            "material": record["material"],
            "symptoms": record["symptoms"],
            "region_id": record["region_id"],
            "region_name": record["region_name"],
            "photo_observations": record["photo_observations"],
            "photos": storage.signed_photos(record["photo_files"]),
            "input_revision": current_revision,
            "questions": questions,
            "messages": messages,
            "next_question": next_question,
            "diagnosis": diagnosis,
            "drafts": {
                "landlord": _draft_out(
                    record["landlord_draft"],
                    record["landlord_draft_revision"],
                    record["landlord_draft_diagnosis_generation"],
                    current_revision,
                    current_generation,
                ),
                "provider": _draft_out(
                    record["provider_draft"],
                    record["provider_draft_revision"],
                    record["provider_draft_diagnosis_generation"],
                    current_revision,
                    current_generation,
                ),
            },
        }


@router.patch(
    "/{record_id}",
    response_model=RecordPatchResponse,
    summary="하자 기록 위치·증상 수정",
    description=(
        "하자 기록의 `location`·`material`·`symptoms`·`region_id`를 부분 수정합니다.\n\n"
        "- `location`, `material`, `symptoms`, `region_id` 중 최소 하나를 포함해야 하며, 허용되지 않은 추가 필드는 거부됩니다(`422`).\n"
        "- `region_id`는 `regions`에 존재해야 하며(`422`), `null`이면 지역 스냅샷을 지웁니다.\n"
        '- 생략한 필드는 기존 값을 유지하고, 명시적으로 `null`을 전달한 필드(예: `{"location": null}`)는 값을 지웁니다.\n'
        "- `input_revision`을 요구하지 않으며, 저장된 값과 실제로 달라질 때만 `input_revision`이 `1` 증가합니다(동일 값 재저장 시 유지)."
    ),
    response_description="수정된 위치·증상과 현재 입력 버전",
    responses={
        404: _RECORD_NOT_FOUND_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def update_record(
    record_id: Annotated[UUID, Path(description="수정할 하자 기록의 UUID.")],
    body: Annotated[
        RecordPatchRequest,
        Body(
            openapi_examples={
                "update_fields": {
                    "summary": "위치·재질·증상 수정",
                    "value": {
                        "location": "안방 창틀 아래",
                        "material": "실리콘",
                        "symptoms": "검은 곰팡이 얼룩이 번지고 있어요",
                    },
                },
                "update_symptoms_only": {
                    "summary": "증상만 부분 수정(위치·재질 유지)",
                    "value": {
                        "symptoms": "벽지가 들뜨고 물기가 맺혀 있어요",
                    },
                },
            }
        ),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = _lock_record(conn, record_id, owner_id)
        location = body.location if "location" in body.model_fields_set else record["location"]
        material = body.material if "material" in body.model_fields_set else record["material"]
        symptoms = body.symptoms if "symptoms" in body.model_fields_set else record["symptoms"]
        region_id = (
            body.region_id if "region_id" in body.model_fields_set else record["region_id"]
        )
        _validate_region(conn, region_id)

        if (
            location == record["location"]
            and material == record["material"]
            and symptoms == record["symptoms"]
            and region_id == record["region_id"]
        ):
            return {
                "record_id": record["id"],
                "location": location,
                "material": material,
                "symptoms": symptoms,
                "region_id": region_id,
                "input_revision": record["input_revision"],
            }

        updated = conn.execute(
            """
            UPDATE records
            SET location = %s, material = %s, symptoms = %s, region_id = %s,
                input_revision = input_revision + 1, updated_at = now()
            WHERE id = %s
            RETURNING location, material, symptoms, region_id, input_revision
            """,
            (location, material, symptoms, region_id, record_id),
        ).fetchone()
    return {"record_id": record_id, **updated}


@router.post(
    "/{record_id}/analyze",
    response_model=AnalyzeResponse,
    summary="사진·위치·재질 일괄 분석",
    description=(
        "사진 1~2장과 위치·재질·선택 증상 메모를 multipart로 한 번에 받아 사진 관찰과 AI 진단을 저장합니다.\n\n"
        "- `YOLO_MODEL_PATH` 설정 시 YOLO 사진 탐지를 수행합니다. 외부 분석 동의와 `MODEL_API_KEY`가 있으면 Meta SAM 3.1로 탐지 영역을 분할하고 화면 점유 비율(`area_ratio`)을 계산합니다.\n"
        "- 사진별로 YOLO 탐지가 없거나 YOLO를 실행할 수 없으면, 동의와 `LLM_API_KEY`가 있을 때 그 사진만 비전 LLM으로 독립 관찰합니다. 두 방법이 모두 실패하거나 판독할 수 없어도 전체 분석을 실패시키지 않고 사진 상태(`failed` 또는 `analyzed`)를 기록합니다.\n"
        "- `YOLO_MODEL_PATH`와 `LLM_API_KEY`가 모두 미설정이면 기존 샘플 모드(`source=sample`)입니다. `YOLO_MODEL_PATH`만 설정하고 `LLM_API_KEY`가 없으면 `503`(`llm_unavailable`)입니다.\n"
        "- 진단 모델이 설정된 경우, 사진 관찰 요약과 마스킹한 위치·재질·증상, DB 작업 종류로 구조화 진단을 생성합니다. 모델 호출·형식 오류는 `502`, 제한 시간 초과는 `504`이며 이때 기존 저장 결과를 유지합니다.\n"
        "- 탐지 결과·박스·신뢰도·마스크·화면 점유 비율은 저장하며 사진 원본은 저장하지 않습니다. 사진당 최대 16개를 탐지합니다.\n"
        "- 선택 `region_id`는 분석 전 지역 확인 값입니다. 전달하면 `regions` 존재를 검증하고, 생략하면 기존 기록의 지역 또는 프로필 거주 지역을 스냅샷으로 저장합니다. 지역이 실제로 바뀌면 `input_revision`이 증가합니다.\n"
        "- 사진은 1~2장, JPEG/PNG/HEIC/HEIF, 한 장당 10MB 이하만 허용합니다. `photo_roles`는 사진 수와 같아야 하며 서로 달라야 합니다.\n"
        "- 제출한 위치·재질·증상이 실제로 바뀌면 `input_revision`을 올리고 `diagnosis_generation`을 증가시킵니다. 분석 중 입력이 바뀌면 아무것도 저장하지 않고 `409`를 반환합니다.\n"
        "- 성공·실패 모두 업로드 임시 파일을 닫고, 원본 사진이나 로그는 남기지 않습니다."
    ),
    response_description="사진 분석 결과와 저장된 AI 진단",
    responses={
        404: _RECORD_NOT_FOUND_RESPONSE,
        409: _ANALYZE_CONFLICT_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
        502: _error_response(
            ErrorResponse,
            "진단 모델 호출 또는 응답 형식 오류. 기존 결과는 유지됩니다.",
            {"llm_error": {"summary": "진단 모델 오류", "value": {
                "code": "llm_error", "message": "진단 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            }}},
        ),
        503: _error_response(
            ErrorResponse,
            "사진 분석 의존성·모델 설정 문제. 기존 결과는 유지됩니다.",
            {
                "yolo_unavailable": {"summary": "YOLO 실행 불가", "value": {
                    "code": "yolo_unavailable", "message": "하자 탐지 모델을 실행할 수 없습니다.",
                }},
                "llm_unavailable": {"summary": "진단 모델 키 미설정", "value": {
                    "code": "llm_unavailable", "message": "진단 모델이 설정되지 않았습니다. 서버에 LLM_API_KEY를 설정해 주세요.",
                }},
            },
        ),
        504: _error_response(
            ErrorResponse,
            "진단 모델 제한 시간 초과. 기존 결과는 유지됩니다.",
            {"llm_timeout": {"summary": "진단 모델 시간 초과", "value": {
                "code": "llm_timeout", "message": "진단 생성 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
            }}},
        ),
    },
)
def analyze_record(
    record_id: Annotated[
        UUID,
        Path(description="분석할 하자 기록의 UUID."),
    ],
    photos: Annotated[
        list[UploadFile],
        File(
            description="사진 파일 1~2장. 첫 번째 사진은 필수입니다.",
            json_schema_extra={"items": {"type": "string", "format": "binary"}},
        ),
    ],
    photo_roles: Annotated[
        list[str],
        Form(description="사진별 역할. `overview`(전체) 또는 `closeup`(근접)이며 사진 수와 같아야 합니다."),
    ],
    location: Annotated[
        str,
        Form(description="하자 발견 위치. 공백만 입력할 수 없습니다."),
    ],
    material: Annotated[
        str,
        Form(description="하자 표면 재질. 공백만 입력할 수 없습니다."),
    ],
    symptoms: Annotated[
        str | None,
        Form(description="선택 증상 메모. 없으면 생략하거나 `null`/빈 문자열로 보냅니다."),
    ] = None,
    region_id: Annotated[
        UUID | None,
        Form(description="분석 지역 UUID. 생략하면 기존 기록의 지역, 그것도 없으면 프로필 거주 지역을 스냅샷으로 저장합니다."),
    ] = None,
    external_analysis_consent: Annotated[
        bool,
        Form(description="외부 사진 전송(Meta SAM·비전 LLM) 동의 여부. 생략하면 `false`이며, 명시적 `true`일 때만 사진을 외부 모델로 보냅니다."),
    ] = False,
    owner_id: UUID = Depends(get_current_user),
):
    try:
        with transaction() as conn:
            record = _lock_record(conn, record_id, owner_id)
            snapshot_revision = record["input_revision"]
            if region_id is not None:
                _validate_region(conn, region_id)
                selected_region_id = region_id
            else:
                selected_region_id = record["region_id"]
                if selected_region_id is None:
                    profile = conn.execute(
                        "SELECT region_id FROM profiles WHERE user_id = %s",
                        (owner_id,),
                    ).fetchone()
                    selected_region_id = profile["region_id"] if profile else None
        # The row lock ends before file validation and external calls.

        if not 1 <= len(photos) <= 2:
            raise invalid_request("사진은 1~2장을 업로드해야 합니다.")
        _validate_photo_roles(photo_roles, len(photos))
        for photo in photos:
            _validate_photo(photo)

        location = location.strip()
        material = material.strip()
        symptoms = (symptoms or "").strip() or None
        if not location:
            raise invalid_request("위치를 입력해야 합니다.")
        if not material:
            raise invalid_request("재질을 입력해야 합니다.")

        settings = get_settings()
        if settings.yolo_model_path and not settings.llm_api_key:
            raise diagnosis_llm_unavailable()

        if not settings.yolo_model_path and not settings.llm_api_key:
            sample = build_sample_analysis(
                location=location,
                material=material,
                symptoms=symptoms,
                photo_roles=photo_roles,
                external_analysis_consent=external_analysis_consent,
            )
            photo_analysis = sample.photo_analysis
            diagnosis_result = sample.diagnosis
        else:
            photo_analysis = analyze_photos(
                photos, photo_roles, external_analysis_consent
            )
            work_types = diagnosis.load_work_types()
            try:
                diagnosis_result = diagnosis.generate_diagnosis(
                    {
                        "location": location,
                        "material": material,
                        "symptoms": symptoms,
                        "photo_observations": photo_analysis,
                    },
                    work_types,
                )
            except llm.LlmUnavailable:
                raise diagnosis_llm_unavailable() from None
            except llm.LlmQuotaExceeded:
                raise llm_quota_exceeded() from None
            except llm.LlmTimeout:
                raise diagnosis_llm_timeout() from None
            except llm.LlmError:
                raise diagnosis_llm_failed() from None

        uploaded_paths: list[str] = []
        photo_files: list[dict] = []
        if storage.is_configured():
            try:
                for photo, role in zip(photos, photo_roles, strict=True):
                    item = storage.store_photo(photo, owner_id, record_id, role)
                    photo_files.append(item)
                    uploaded_paths.append(item["storage_path"])
            except Exception:
                for path in uploaded_paths:
                    storage.delete_photo(path)
                raise

        try:
            with transaction() as conn:
                record = _lock_record(conn, record_id, owner_id)
                if record["input_revision"] != snapshot_revision:
                    raise revision_conflict(record["input_revision"])

                changed = (
                    location != record["location"]
                    or material != record["material"]
                    or symptoms != record["symptoms"]
                    or selected_region_id != record["region_id"]
                )
                new_revision = record["input_revision"] + (1 if changed else 0)
                updated = conn.execute(
                    """
                    UPDATE records
                    SET location = %s,
                        material = %s,
                        symptoms = %s,
                        region_id = %s,
                        photo_observations = %s,
                        photo_files = %s,
                        diagnosis = %s,
                        diagnosis_revision = %s,
                        diagnosis_generation = diagnosis_generation + 1,
                        input_revision = %s,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING input_revision, diagnosis_generation
                    """,
                    (
                        location,
                        material,
                        symptoms,
                        selected_region_id,
                        Jsonb(photo_analysis),
                        Jsonb(photo_files),
                        Jsonb(diagnosis_result),
                        new_revision,
                        new_revision,
                        record_id,
                    ),
                ).fetchone()
        except Exception:
            for path in uploaded_paths:
                storage.delete_photo(path)
            raise

        return {
            "record_id": record_id,
            "input_revision": updated["input_revision"],
            "diagnosis_generation": updated["diagnosis_generation"],
            "region_id": selected_region_id,
            "photo_analysis": photo_analysis,
            "diagnosis": diagnosis_result,
            "source": photo_analysis["source"],
        }
    finally:
        for photo in photos:
            photo.file.close()


@router.post(
    "/{record_id}/next-question",
    response_model=NextQuestionResponse,
    summary="시연용 다음 질문 조회",
    description=(
        "현재 서버에 저장된 위치·증상과 대화로 다음 시연 질문을 결정합니다.\n\n"
        "- 클라이언트는 사용자 ID나 대화 전체를 보내지 않습니다. 인증 토큰의 사용자와 기록 소유권만 확인합니다.\n"
        "- 실제 LLM이 아니라 곰팡이 의심 창가 얼룩 사례의 두 질문을 사용하는 시연 규칙이며, 응답의 `source`는 항상 `sample`입니다.\n"
        "- 같은 `input_revision`의 완료 응답이 있으면 질문·AI 메시지를 다시 만들지 않고 저장 결과를 반환합니다. 생성 중 입력이 바뀌면 `409`를 반환하고 아무것도 저장하지 않습니다.\n"
        "- 질문과 AI 응답을 저장해도 `input_revision`은 증가하지 않습니다."
    ),
    response_description="다음 질문 또는 종료 응답과 사용한 입력 버전",
    responses={
        404: _RECORD_NOT_FOUND_RESPONSE,
        409: _NEXT_QUESTION_CONFLICT_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def next_question(
    record_id: Annotated[
        UUID,
        Path(description="다음 질문을 조회할 하자 기록의 UUID."),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = _lock_record(conn, record_id, owner_id)
        cached = _current_next_question_result(record)
        if cached is not None:
            return cached

        snapshot_revision = record["input_revision"]
        state = {
            "input_revision": snapshot_revision,
            "location": record["location"],
            "symptoms": record["symptoms"],
            **_load_next_question_state(conn, record_id),
        }
    # The row lock ends here; the sample decision is computed from a snapshot,
    # and the final version check below prevents stale results from being saved.

    decision = build_sample_decision(state)

    with transaction() as conn:
        record = _lock_record(conn, record_id, owner_id)
        if record["input_revision"] != snapshot_revision:
            raise revision_conflict(record["input_revision"])

        cached = _current_next_question_result(record)
        if cached is not None:
            return cached

        for question_id in decision.answered_question_ids:
            conn.execute(
                """
                UPDATE questions SET answered = TRUE
                WHERE id = %s AND record_id = %s
                """,
                (question_id, record_id),
            )

        if decision.reply is not None:
            reply_sequence = _allocate_conversation_sequence(conn, record_id)
            conn.execute(
                """
                INSERT INTO messages
                    (record_id, question_id, sequence, sender, content,
                     input_revision)
                VALUES (%s, %s, %s, 'assistant', %s, %s)
                """,
                (
                    record_id,
                    decision.reply_question_id,
                    reply_sequence,
                    decision.reply,
                    snapshot_revision,
                ),
            )

        question = decision.question
        if question is not None and question["id"] is None:
            question_sequence = _allocate_conversation_sequence(conn, record_id)
            question = conn.execute(
                """
                INSERT INTO questions
                    (record_id, sequence, content, options, answered, input_revision)
                VALUES (%s, %s, %s, %s, FALSE, %s)
                RETURNING id, content, options
                """,
                (
                    record_id,
                    question_sequence,
                    question["content"],
                    Jsonb(question["options"]),
                    snapshot_revision,
                ),
            ).fetchone()

        result = {
            "input_revision": snapshot_revision,
            "reply": decision.reply,
            "question": (
                {
                    "id": str(question["id"]),
                    "content": question["content"],
                    "options": question["options"],
                }
                if question is not None
                else None
            ),
            "ready_for_diagnosis": decision.ready_for_diagnosis,
            "source": SOURCE,
        }
        conn.execute(
            """
            UPDATE records
            SET next_question_result = %s,
                next_question_revision = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (Jsonb(result), snapshot_revision, record_id),
        )
    return result


@router.post(
    "/{record_id}/messages",
    response_model=MessageSaveResponse,
    summary="사용자 메시지(답변) 저장",
    description=(
        "사용자 메시지(질문 답변 또는 자유 입력)를 저장하고 공용 `sequence`를 할당하며 `input_revision`을 `1` 증가시킵니다.\n\n"
        "- **입력 규칙**: `content`와 `selected_option_id` 중 정확히 하나만 보내야 합니다. `selected_option_id`를 보낼 때는 `question_id`가 필수이며, 서버에 저장된 선택지 `label`을 메시지 `content`로 저장합니다. `content`는 공백만 입력할 수 없습니다.\n"
        "- **멱등성(재전송)**: 기록 소유권 확인 후 `input_revision` 검사 전에 `client_message_id`를 조회합니다. 최초 `POST`의 `question_id`·`selected_option_id`·직접 입력 `content`가 동일하면(`input_revision` 제외) 기존 저장 메시지(이후 `PUT`으로 수정된 경우 수정본 포함)와 현재 `input_revision`을 반환합니다. 같은 ID로 다른 내용·질문·선택지를 보내면 `409`(`message_conflict`)를 반환합니다.\n"
        "- **버전 검사**: 새 메시지 저장 시 본문의 `input_revision`이 서버 최신 버전과 다르면 `409`(`revision_conflict`)와 현재 `input_revision`을 반환합니다."
    ),
    response_description="저장된 사용자 메시지와 현재 기록 입력 버전",
    responses={
        404: _MESSAGE_POST_NOT_FOUND_RESPONSE,
        409: _MESSAGE_POST_CONFLICT_RESPONSE,
        422: _MESSAGE_POST_VALIDATION_ERROR_RESPONSE,
    },
)
def create_message(
    record_id: Annotated[UUID, Path(description="메시지를 저장할 하자 기록의 UUID.")],
    body: Annotated[
        MessageCreateRequest,
        Body(
            openapi_examples={
                "direct_input": {
                    "summary": "직접 입력 답변",
                    "value": {
                        "client_message_id": "8a5f2f4e-2c1b-4a3a-9b8e-1d2f3a4b5c6d",
                        "content": "창틀 아래에 검은 곰팡이가 있어요",
                        "input_revision": 0,
                    },
                },
                "selected_option": {
                    "summary": "선택지 선택 답변",
                    "value": {
                        "client_message_id": "2c1b4a3a-9b8e-4d2f-8a5f-1d2f3a4b5c6d",
                        "question_id": "550e8400-e29b-41d4-a716-446655440000",
                        "selected_option_id": "recurred",
                        "input_revision": 1,
                    },
                },
            }
        ),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = _lock_record(conn, record_id, owner_id)

        existing = conn.execute(
            f"""
            SELECT {_MESSAGE_COLUMNS}, selected_option_id, submitted_content FROM messages
            WHERE record_id = %s AND client_message_id = %s AND sender = 'user'
            """,
            (record_id, body.client_message_id),
        ).fetchone()
        if existing is not None:
            if (
                existing["question_id"] != body.question_id
                or existing["selected_option_id"] != body.selected_option_id
                or existing["submitted_content"] != body.content
            ):
                raise message_conflict(record["input_revision"])
            return {"message": existing, "input_revision": record["input_revision"]}

        content = _answer_content(conn, record_id, body)
        if body.input_revision != record["input_revision"]:
            raise revision_conflict(record["input_revision"])

        allocated = conn.execute(
            """
            UPDATE records
            SET conversation_sequence = conversation_sequence + 1,
                input_revision = input_revision + 1, updated_at = now()
            WHERE id = %s
            RETURNING conversation_sequence, input_revision
            """,
            (record_id,),
        ).fetchone()
        message = conn.execute(
            f"""
            INSERT INTO messages
                (record_id, question_id, sequence, sender, content,
                 client_message_id, input_revision, selected_option_id, submitted_content)
            VALUES (%s, %s, %s, 'user', %s, %s, %s, %s, %s)
            RETURNING {_MESSAGE_COLUMNS}
            """,
            (
                record_id,
                body.question_id,
                allocated["conversation_sequence"],
                content,
                body.client_message_id,
                allocated["input_revision"],
                body.selected_option_id,
                body.content,
            ),
        ).fetchone()
    return {"message": message, "input_revision": allocated["input_revision"]}


@router.put(
    "/{record_id}/messages/{message_id}",
    response_model=MessageSaveResponse,
    summary="과거 사용자 메시지 수정",
    description=(
        "이미 저장된 사용자(`sender: \"user\"`) 메시지의 내용을 수정합니다.\n\n"
        "- **처리 순서**: 기록 소유권 확인 → `input_revision` 검사 → 수정 대상 메시지 조회 순서로 처리합니다. 버전이 오래되었으면 대상 메시지 존재 여부나 내용 동일 여부와 무관하게 `409`(`revision_conflict`)와 현재 `input_revision`을 반환합니다. 버전이 일치할 때 메시지가 없거나 `assistant` 메시지이면 `404`를 반환합니다.\n"
        "- **후속 대화 삭제**: 수정하려는 `content`가 기존과 같으면 삭제·버전 증가 없이 `200`을 반환합니다. 내용이 다르면 같은 트랜잭션에서 해당 메시지의 `sequence`보다 큰 모든 후속 메시지와 질문을 삭제하고 내용을 갱신하며 `input_revision`을 `1` 증가시킵니다."
    ),
    response_description="수정된 사용자 메시지와 갱신된 기록 입력 버전",
    responses={
        404: _MESSAGE_PUT_NOT_FOUND_RESPONSE,
        409: _MESSAGE_PUT_CONFLICT_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def update_message(
    record_id: Annotated[UUID, Path(description="수정할 메시지가 속한 하자 기록의 UUID.")],
    message_id: Annotated[
        UUID,
        Path(
            description="수정할 사용자 메시지의 UUID. `sender`가 `user`인 메시지만 수정할 수 있습니다."
        ),
    ],
    body: Annotated[
        MessageUpdateRequest,
        Body(
            openapi_examples={
                "edit_message": {
                    "summary": "메시지 내용 수정",
                    "value": {
                        "content": "닦은 뒤 일주일 만에 다시 생겼어요",
                        "input_revision": 2,
                    },
                }
            }
        ),
    ],
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = _lock_record(conn, record_id, owner_id)
        if body.input_revision != record["input_revision"]:
            raise revision_conflict(record["input_revision"])

        message = conn.execute(
            f"""
            SELECT {_MESSAGE_COLUMNS} FROM messages
            WHERE id = %s AND record_id = %s AND sender = 'user'
            FOR UPDATE
            """,
            (message_id, record_id),
        ).fetchone()
        if message is None:
            raise not_found("메시지를 찾을 수 없어요.")

        if message["content"] == body.content:
            return {"message": message, "input_revision": record["input_revision"]}

        conn.execute(
            "DELETE FROM messages WHERE record_id = %s AND sequence > %s",
            (record_id, message["sequence"]),
        )
        conn.execute(
            "DELETE FROM questions WHERE record_id = %s AND sequence > %s",
            (record_id, message["sequence"]),
        )
        if message["question_id"] is not None:
            conn.execute(
                """
                UPDATE questions SET answered = FALSE
                WHERE id = %s AND record_id = %s
                """,
                (message["question_id"], record_id),
            )
        new_revision = conn.execute(
            """
            UPDATE records
            SET input_revision = input_revision + 1,
                next_question_result = NULL,
                next_question_revision = NULL,
                updated_at = now()
            WHERE id = %s
            RETURNING input_revision
            """,
            (record_id,),
        ).fetchone()["input_revision"]
        updated = conn.execute(
            f"""
            UPDATE messages SET content = %s, input_revision = %s
            WHERE id = %s
            RETURNING {_MESSAGE_COLUMNS}
            """,
            (body.content, new_revision, message_id),
        ).fetchone()
    return {"message": updated, "input_revision": new_revision}
