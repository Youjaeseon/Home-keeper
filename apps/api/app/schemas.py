from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    """서버 상태 확인 응답."""

    status: Literal["ok"] = Field(
        description="서버 상태 값 (`ok`).",
        examples=["ok"],
    )


class ErrorResponse(BaseModel):
    """공통 오류 응답."""

    code: str = Field(
        description="오류 유형을 구분하는 코드 (예: `unauthorized`, `not_found`, `invalid_request`, `internal_error`).",
        examples=["not_found"],
    )
    message: str = Field(
        description="사용자에게 안내할 한국어 오류 메시지.",
        examples=["기록을 찾을 수 없습니다."],
    )


class ConflictErrorResponse(ErrorResponse):
    """입력 버전 충돌(`revision_conflict`) 또는 동일 `client_message_id` 내용 충돌(`message_conflict`) 시 반환되는 409 오류 응답."""

    input_revision: int = Field(
        description="충돌 시점의 서버 최신 기록 입력 버전(`input_revision`). 최신 기록을 확인한 뒤 이 버전으로 다시 요청해야 합니다.",
        examples=[2],
    )


class RecordCreateResponse(BaseModel):
    """하자 기록 생성 응답."""

    record_id: UUID = Field(description="생성된 하자 기록의 고유 UUID.")
    input_revision: int = Field(description="초기 입력 버전. 최초 생성 시 `0`입니다.")


class RecordPatchRequest(BaseModel):
    """하자 기록 위치·증상 부분 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = Field(
        default=None,
        description="하자 발견 위치(예: 안방 창틀 아래). 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )
    symptoms: str | None = Field(
        default=None,
        description="하자 증상 설명(예: 검은 곰팡이 얼룩). 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )

    @model_validator(mode="after")
    def require_a_field(self):
        if not self.model_fields_set:
            raise ValueError("location 또는 symptoms 중 하나가 필요해요.")
        return self


class RecordPatchResponse(BaseModel):
    """하자 기록 위치·증상 수정 응답."""

    record_id: UUID = Field(description="수정한 하자 기록의 UUID.")
    location: str | None = Field(description="저장된 하자 발견 위치(값이 없으면 `null`).")
    symptoms: str | None = Field(description="저장된 하자 증상 설명(값이 없으면 `null`).")
    input_revision: int = Field(
        description="요청 처리 후 현재 기록 입력 버전. 실제 값이 변경된 경우에만 `1` 증가합니다."
    )


class QuestionOption(BaseModel):
    """질문에 제시되는 단일 선택지 항목."""

    id: str = Field(
        description="선택지 식별 ID. 선택 답변 저장 시 `selected_option_id`로 전달합니다."
    )
    label: str = Field(
        description="화면에 표시되며 선택 시 사용자 메시지 `content`로 저장되는 문구."
    )


class QuestionOut(BaseModel):
    """하자 기록에 포함된 AI 질문 정보."""

    id: UUID = Field(description="질문의 고유 UUID.")
    record_id: UUID = Field(description="질문이 속한 하자 기록의 UUID.")
    sequence: int = Field(
        description="기록 내 대화 공용 순번. `messages.sequence`와 합쳐 정렬하면 전체 대화 순서가 유지됩니다."
    )
    content: str = Field(description="사용자에게 제시하는 질문 문구.")
    options: list[QuestionOption] = Field(
        description="제시된 선택지 목록. 자유 입력 질문이면 빈 배열입니다."
    )
    answered: bool = Field(description="질문에 필요한 정보가 확인되었는지 여부.")
    input_revision: int = Field(description="질문이 생성된 시점의 기록 입력 버전.")
    created_at: datetime = Field(description="질문 생성 시각(UTC).")


class MessageOut(BaseModel):
    """하자 기록에 저장된 대화 메시지 정보."""

    id: UUID = Field(description="메시지의 고유 UUID.")
    record_id: UUID = Field(description="메시지가 속한 하자 기록의 UUID.")
    question_id: UUID | None = Field(
        description="연결된 질문의 UUID. 특정 질문과 연결되지 않은 자유 메시지면 `null`입니다."
    )
    sequence: int = Field(
        description="기록 내 대화 공용 순번. `questions.sequence`와 합쳐 정렬하면 전체 대화 순서가 유지됩니다."
    )
    sender: Literal["user", "assistant"] = Field(
        description="메시지 발신자 구분 (`user` 또는 `assistant`)."
    )
    content: str = Field(
        description="저장된 메시지 본문. 선택지 답변은 서버가 확인한 선택지 `label`이 저장됩니다."
    )
    client_message_id: UUID | None = Field(
        description="클라이언트가 발급한 재전송 멱등성 식별 UUID. `assistant` 메시지는 `null`입니다."
    )
    input_revision: int = Field(
        description="메시지 저장 또는 마지막 수정 시점의 기록 입력 버전."
    )
    created_at: datetime = Field(description="메시지 생성 시각(UTC).")


class MessageCreateRequest(BaseModel):
    """사용자 메시지(질문 답변 또는 자유 입력) 저장 요청."""

    model_config = ConfigDict(extra="forbid")

    client_message_id: UUID = Field(
        description="클라이언트가 생성한 메시지 고유 UUID(재전송 멱등성 식별자)."
    )
    question_id: UUID | None = Field(
        default=None,
        description="답변 대상 질문의 UUID. `selected_option_id`를 보낼 때는 필수입니다.",
    )
    content: str | None = Field(
        default=None,
        description="직접 입력한 답변 문구(공백만 불가). `selected_option_id`와 동시에 보낼 수 없습니다.",
    )
    selected_option_id: str | None = Field(
        default=None,
        description="선택한 질문 선택지의 ID. `question_id`가 필수이며 `content`와 동시에 보낼 수 없습니다.",
    )
    input_revision: int = Field(
        ge=0,
        description="클라이언트가 확인한 현재 기록 입력 버전(`0` 이상). 서버 버전과 다르면 `409`가 반환됩니다.",
    )

    @model_validator(mode="after")
    def validate_answer(self):
        if (self.content is None) == (self.selected_option_id is None):
            raise ValueError("content 또는 selected_option_id 중 정확히 하나가 필요해요.")
        if self.content is not None and not self.content.strip():
            raise ValueError("content는 비어 있을 수 없어요.")
        if self.selected_option_id is not None:
            if not self.selected_option_id.strip():
                raise ValueError("selected_option_id는 비어 있을 수 없어요.")
            if self.question_id is None:
                raise ValueError("선택 답변에는 question_id가 필요해요.")
        return self


class MessageUpdateRequest(BaseModel):
    """과거 사용자 메시지 내용 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(
        min_length=1,
        description="수정할 새 메시지 내용(공백만 불가).",
    )
    input_revision: int = Field(
        ge=0,
        description="편집 시작 시 확인한 현재 기록 입력 버전(`0` 이상). 서버 버전과 다르면 `409`가 반환됩니다.",
    )

    @model_validator(mode="after")
    def reject_blank(self):
        if not self.content.strip():
            raise ValueError("content는 비어 있을 수 없어요.")
        return self


class MessageSaveResponse(BaseModel):
    """사용자 메시지 저장 또는 수정 응답."""

    message: MessageOut = Field(
        description="저장·수정된 메시지 또는 재전송 시 기존에 저장된 메시지."
    )
    input_revision: int = Field(description="요청 처리 후 현재 기록 입력 버전.")


class NextQuestionOut(BaseModel):
    """저장된 다음 질문 생성 결과."""

    result: Any = Field(description="다음 질문 생성 API의 저장 결과 JSON.")
    input_revision: int | None = Field(description="결과 생성에 사용한 기록 입력 버전.")
    is_current: bool = Field(
        description="결과가 현재 `input_revision`과 일치하는 최신 결과인지 여부."
    )


class DiagnosisOut(BaseModel):
    """저장된 하자 진단 결과."""

    diagnosis: Any = Field(
        description="진단 생성 API가 저장한 진단 JSON(심각도, 판단 이유, 권장 행동 등)."
    )
    input_revision: int | None = Field(description="진단 생성에 사용한 기록 입력 버전.")
    generation: int = Field(
        description="진단 생성 번호(`diagnosis_generation`). 진단 재생성 시 증가합니다."
    )
    is_current: bool = Field(
        description="진단이 현재 `input_revision`과 일치하는 최신 결과인지 여부."
    )


class DraftOut(BaseModel):
    """저장된 점검 요청문 또는 견적 요청문 초안."""

    text: str = Field(description="생성된 요청문 본문.")
    input_revision: int | None = Field(description="요청문 생성에 사용한 기록 입력 버전.")
    diagnosis_generation: int | None = Field(
        description="요청문 생성에 사용한 진단 생성 번호."
    )
    is_current: bool = Field(
        description="현재 `input_revision` 및 `diagnosis_generation` 모두와 일치하는 최신 요청문인지 여부."
    )


class DraftsOut(BaseModel):
    """임대인 점검 요청문 및 업체 견적 요청문 묶음."""

    landlord: DraftOut | None = Field(
        description="임대인·관리실 점검 요청문. 아직 생성되지 않았으면 `null`입니다."
    )
    provider: DraftOut | None = Field(
        description="업체 견적 요청문. 아직 생성되지 않았으면 `null`입니다."
    )


class RecordOut(BaseModel):
    """하자 기록 상세 조회 응답."""

    record_id: UUID = Field(description="하자 기록의 고유 UUID.")
    location: str | None = Field(
        description="사용자가 입력한 하자 발견 위치(미입력 시 `null`)."
    )
    symptoms: str | None = Field(
        description="사용자가 입력한 하자 증상 설명(미입력 시 `null`)."
    )
    photo_observations: Any = Field(
        default=None,
        description="사진 분석으로 저장된 관찰 결과 JSON(원본 사진·좌표 미저장, 미분석 시 `null`).",
    )
    input_revision: int = Field(description="현재 기록 입력 버전.")
    questions: list[QuestionOut] = Field(
        description="공용 `sequence` 오름차순으로 정렬된 AI 질문 목록."
    )
    messages: list[MessageOut] = Field(
        description="공용 `sequence` 오름차순으로 정렬된 대화 메시지 목록."
    )
    next_question: NextQuestionOut | None = Field(
        description="마지막 다음 질문 생성 결과(미생성 시 `null`)."
    )
    diagnosis: DiagnosisOut | None = Field(
        description="마지막 하자 진단 결과(미생성 시 `null`)."
    )
    drafts: DraftsOut = Field(
        description="임대인 점검 요청문(`landlord`)과 업체 견적 요청문(`provider`) 정보."
    )
