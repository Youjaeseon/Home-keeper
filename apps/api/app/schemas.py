from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HousingType = Literal["monthly_rent", "jeonse", "semi_jeonse", "owned", "other"]
DeadlineKind = Literal["fixed", "always_open", "unknown"]
SupportProgramSource = Literal["seed", "gov24_api"]


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
    """하자 기록 위치·재질·증상 부분 수정 요청."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = Field(
        default=None,
        description="하자 발견 위치(예: 안방 창틀 아래). 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )
    material: str | None = Field(
        default=None,
        description="하자 표면 재질(예: 실리콘, 벽지, 도장면). 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )
    symptoms: str | None = Field(
        default=None,
        description="하자 증상 설명(예: 검은 곰팡이 얼룩). 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )
    region_id: UUID | None = Field(
        default=None,
        description="분석 지역 스냅샷 UUID. 생략하면 기존 값을 유지하고 `null`을 보내면 값을 지웁니다.",
    )

    @model_validator(mode="after")
    def require_a_field(self):
        if not self.model_fields_set:
            raise ValueError("location, material, symptoms, region_id 중 하나가 필요해요.")
        return self


class RecordPatchResponse(BaseModel):
    """하자 기록 위치·재질·증상 수정 응답."""

    record_id: UUID = Field(description="수정한 하자 기록의 UUID.")
    location: str | None = Field(description="저장된 하자 발견 위치(값이 없으면 `null`).")
    material: str | None = Field(description="저장된 하자 표면 재질(값이 없으면 `null`).")
    symptoms: str | None = Field(description="저장된 하자 증상 설명(값이 없으면 `null`).")
    region_id: UUID | None = Field(
        description="저장된 분석 지역 스냅샷 UUID. 지역이 없으면 `null`입니다."
    )
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


class NextQuestionOption(BaseModel):
    """시연용 다음 질문의 선택지."""

    id: str = Field(
        description="선택지 식별 ID. 사용자 메시지 저장 시 `selected_option_id`로 전달합니다."
    )
    label: str = Field(
        description="화면에 표시되며 선택 시 사용자 메시지 `content`로 저장되는 문구."
    )


class NextQuestionQuestion(BaseModel):
    """다음 질문 조회 응답에 포함되는 질문."""

    id: UUID = Field(description="질문의 고유 UUID.")
    content: str = Field(description="사용자에게 제시하는 질문 문구.")
    options: list[NextQuestionOption] = Field(
        description="질문에 제시되는 선택지 목록. 선택지는 질문 안에서 고유한 ID를 가집니다."
    )


class NextQuestionResponse(BaseModel):
    """시연용 다음 질문 조회 응답."""

    input_revision: int = Field(
        description="이 응답을 생성할 때 사용한 기록 입력 버전. 질문·응답 저장만으로는 증가하지 않습니다."
    )
    reply: str | None = Field(
        description="AI의 짧은 반응. 없으면 `null`입니다."
    )
    question: NextQuestionQuestion | None = Field(
        description="다음 질문. 추가 질문이 없으면 `null`입니다."
    )
    ready_for_diagnosis: bool = Field(
        description="더 확인할 질문이 없으면 `true`, 다음 질문이 있으면 `false`입니다."
    )
    source: Literal["sample"] = Field(
        description="실제 LLM이나 자연어 이해가 아닌 시연용 샘플 규칙으로 생성된 응답임을 표시합니다. 값은 항상 `sample`입니다.",
        examples=["sample"],
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


class VisionObservationOut(BaseModel):
    """비전 LLM의 독립 사진 관찰 요약."""

    suspected_types: list[str] = Field(
        description="사진에서 보인 의심 하자 유형. `균열`, `벗겨짐`, `곰팡이` 중 해당 항목이며 없으면 빈 배열입니다."
    )
    summary: str = Field(description="사진에서 보인 흔적 요약. 판독 불가 시 빈 문자열입니다.")
    approximate_location: str | None = Field(
        description="사진 안에서의 대략적 위치 요약. 판단할 수 없으면 `null`입니다."
    )
    unreadable_reason: str | None = Field(
        description="흐림·어두움 등으로 판독할 수 없을 때의 이유. 판독했으면 `null`입니다."
    )


class AnalyzePhotoOut(BaseModel):
    """사진 일괄 분석의 사진별 처리 상태."""

    role: Literal["overview", "closeup"] = Field(
        description="사진 역할. `overview`는 전체, `closeup`은 근접 사진입니다."
    )
    status: Literal["not_analyzed", "analyzed", "failed"] = Field(
        description="사진 분석 상태. `not_analyzed`는 분석 미수행, `failed`는 YOLO·비전 LLM 모두 실패 또는 판독 불가입니다."
    )
    source: Literal["sample", "yolo", "yolo_sam", "vision_llm"] = Field(
        description="사진 분석 출처: sample, yolo, yolo_sam, vision_llm."
    )
    detections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="탐지 목록. object_id, class_id, label, raw_label, confidence, bbox(반열린 xyxy), image_size, area_ratio, source, segmentation_status, mask를 포함합니다. area_ratio는 이미지 전체 면적 대비 점유 비율(0~1)입니다. mask는 null 또는 COCO RLE(size=[높이,너비], counts)와 시각화용 svg_path, 원본 기준 반열린 bounds, source입니다. segmentation_status는 completed, no_mask, failed, unavailable, skipped_no_consent입니다. 샘플·비전 LLM 분석에서는 빈 배열입니다.",
    )
    vision_observation: VisionObservationOut | None = Field(
        default=None,
        description="YOLO가 읽지 못한 사진을 비전 LLM이 독립 관찰한 요약. 비전 LLM을 호출하지 않았거나 실패하면 `null`입니다.",
    )


class AnalyzePhotoAnalysisOut(BaseModel):
    """사진 일괄 분석의 사진 분석 영역."""

    applied: bool = Field(
        description="실제 사진 분석이 적용됐는지 여부. 샘플 모드에서는 항상 `false`입니다."
    )
    notice: str | None = Field(
        description="사진 분석을 수행하지 않은 이유와 샘플 안내. 샘플 모드에서는 필수입니다."
    )
    photos: list[AnalyzePhotoOut] = Field(
        description="업로드한 사진별 역할과 처리 상태 목록."
    )
    source: Literal[
        "sample", "yolo", "yolo_sam", "vision_llm", "yolo_vision_llm"
    ] = Field(
        description="사진 분석 출처. 사진마다 YOLO와 비전 LLM이 섞이면 `yolo_vision_llm`입니다."
    )


class AnalyzeDiagnosisOut(BaseModel):
    """일괄 분석이 저장한 구조화 진단 결과."""

    observations: str = Field(
        description="입력값을 바탕으로 한 관찰 요약. 샘플 모드에서는 사진 분석 미수행을 명시합니다."
    )
    suspected_types: list[str] = Field(
        description="입력에서 의심한 하자 유형 목록(예: `곰팡이`, `균열`, `벗겨짐`). 목록 API 요약에 사용합니다."
    )
    severity_score: int | None = Field(
        ge=0,
        le=100,
        description="심각도 퍼센트(0~100). 정보가 부족한 실제 모델 결과에서는 `null`일 수 있습니다.",
    )
    severity_level: Literal["low", "medium", "high", "undetermined"] = Field(
        description="심각도 단계. `undetermined`는 판단 보류입니다."
    )
    reason: str = Field(description="심각도와 권장 대응의 산정 근거.")
    causes: list[str] = Field(description="추정 원인 목록. 확정 원인이 아닙니다.")
    estimation_notice: str = Field(
        description="AI/샘플 추정임을 알리는 안내. 실제 사진 분석이나 현장 점검 결과가 아님을 표시합니다."
    )
    recommended_action: Literal["self_care", "inspection", "provider_consult"] = Field(
        description="권장 대응. 직접 조치, 점검 요청, 업체 상담 중 하나입니다."
    )
    care_steps: list[str] = Field(description="해결방안과 처리 단계 목록.")
    supplies: list[str] = Field(description="처리에 필요한 준비물 목록.")
    prevention_tips: list[str] = Field(description="재발 방지책 목록.")
    unknowns: list[str] = Field(description="아직 확인되지 않은 정보 목록.")
    work_type_id: UUID | None = Field(
        description="추천 작업 종류의 UUID. 샘플 모드에서는 작업 목록이 없으면 `null`입니다."
    )
    work_type_reason: str = Field(description="추천 작업과 원인 점검을 권장하는 이유.")
    source: Literal["llm", "sample"] = Field(
        description="진단 출처. 실제 모델 생성이면 `llm`, 샘플 규칙이면 `sample`입니다."
    )


class AnalyzeResponse(BaseModel):
    """사진·위치·재질·증상 일괄 분석 응답."""

    record_id: UUID = Field(description="분석한 하자 기록의 UUID.")
    input_revision: int = Field(
        description="분석 입력을 저장한 뒤의 기록 입력 버전. 실제 입력 변경 시에만 증가합니다."
    )
    diagnosis_generation: int = Field(
        description="진단 생성 번호. 분석 성공 시 `1` 증가합니다."
    )
    region_id: UUID | None = Field(
        description="저장된 분석 지역 스냅샷 UUID. 지역이 없으면 `null`입니다."
    )
    photo_analysis: AnalyzePhotoAnalysisOut = Field(
        description="사진별 분석 상태. 샘플 모드에서는 실제 사진 분석을 수행하지 않습니다."
    )
    diagnosis: AnalyzeDiagnosisOut = Field(description="저장된 구조화 진단 결과.")
    source: Literal[
        "sample", "yolo", "yolo_sam", "vision_llm", "yolo_vision_llm"
    ] = Field(
        description="사진 분석 출처. 진단 출처는 diagnosis.source로 별도 표시합니다."
    )


class DiagnosisResponse(BaseModel):
    """진단 생성·재사용 응답."""

    record_id: UUID = Field(description="진단한 하자 기록의 UUID.")
    input_revision: int = Field(description="응답 시점의 기록 입력 버전.")
    diagnosis_generation: int = Field(description="진단 생성 번호.")
    diagnosis: AnalyzeDiagnosisOut = Field(description="저장 또는 재사용된 구조화 진단 결과.")
    source: Literal["llm", "sample"] = Field(
        description="진단 출처. 실제 모델 생성이면 `llm`, 기존 샘플 진단 재사용이면 `sample`입니다."
    )


class SignedPhotoOut(BaseModel):
    """비공개 Storage 사진의 단기 Signed URL."""

    role: Literal["overview", "closeup"] = Field(
        description="사진 역할. `overview`는 전체, `closeup`은 근접 사진입니다."
    )
    url: str = Field(description="단기 만료 Signed URL.")
    expires_at: datetime = Field(description="Signed URL 만료 시각(UTC).")
    width: int = Field(description="저장된 사진 너비(px).")
    height: int = Field(description="저장된 사진 높이(px).")


class QuoteRequestCreateRequest(BaseModel):
    """견적 요청서 생성 요청."""

    model_config = ConfigDict(extra="forbid")

    record_id: UUID = Field(description="요청서로 공개할 본인 하자 기록 UUID.")
    region_id: UUID | None = Field(
        default=None,
        description="요청 지역 UUID. 생략하면 기록의 지역, 그것도 없으면 프로필 거주 지역을 사용합니다.",
    )
    work_type_id: UUID | None = Field(
        default=None,
        description="희망 특화 분야 UUID. 생략하면 진단의 추천 작업, 그것도 없으면 `원인 점검`을 사용합니다.",
    )
    address: str | None = Field(
        default=None, description="선택 장소·주소 메모. 없으면 `null`입니다."
    )
    memo: str | None = Field(
        default=None,
        description="선택 요청 메모. 생략하면 기록의 증상 메모를 사용합니다.",
    )


class QuoteProposalCreateRequest(BaseModel):
    """업체 제안서 제출 요청."""

    model_config = ConfigDict(extra="forbid")

    min_price: int = Field(ge=0, description="최소 견적 금액(원 단위).")
    max_price: int = Field(ge=0, description="최대 견적 금액(원 단위). 최소 금액 이상이어야 합니다.")
    memo: str = Field(
        min_length=1,
        max_length=2000,
        description="제안 조건·작업 범위 메모. 공백만 입력할 수 없으며 최대 2000자입니다.",
    )

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.max_price < self.min_price:
            raise ValueError("최대 금액은 최소 금액 이상이어야 해요.")
        return self

    @field_validator("memo")
    @classmethod
    def memo_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("제안 메모는 공백일 수 없어요.")
        return value


class QuoteProposalOut(BaseModel):
    """견적 요청서에 도착한 업체 제안서."""

    proposal_id: UUID = Field(description="제안서 UUID.")
    created_at: datetime = Field(description="제안서를 보낸 시각(UTC).")
    provider: "ProviderOut" = Field(description="제안 업체 정보.")
    min_price: int = Field(description="최소 견적 금액(원).")
    max_price: int = Field(description="최대 견적 금액(원).")
    memo: str = Field(description="제안 조건·작업 범위 메모.")
    status: Literal["pending", "accepted", "rejected"] = Field(
        description="제안 상태. `pending`은 대기, `accepted`는 수락, `rejected`는 마감입니다."
    )


class QuoteRequestSummary(BaseModel):
    """견적 요청서 목록 항목."""

    request_id: UUID = Field(description="견적 요청서 UUID.")
    record_id: UUID = Field(description="요청서로 공개한 하자 기록 UUID.")
    region_id: UUID = Field(description="요청 지역 UUID.")
    region_name: str = Field(description="요청 지역 표시명.")
    work_type_id: UUID = Field(description="희망 특화 분야 UUID.")
    work_type_name: str = Field(description="희망 특화 분야 이름.")
    requester_nickname: str | None = Field(
        default=None, description="요청인 프로필 닉네임. 업체가 누구의 요청서인지 알아볼 수 있도록 표시합니다. 프로필이 없으면 `null`입니다."
    )
    address: str | None = Field(description="선택 장소·주소 메모. 없으면 `null`입니다.")
    location: str = Field(description="집 안 하자 위치.")
    material: str | None = Field(description="표면 재질. 없으면 `null`입니다.")
    memo: str | None = Field(description="요청 메모. 없으면 `null`입니다.")
    photos: list[SignedPhotoOut] = Field(
        description="요청서 발행 시점 사진 스냅샷의 단기 Signed URL 목록."
    )
    severity_score: int | None = Field(description="AI 심각도 퍼센트. 판단 보류면 `null`입니다.")
    severity_level: Literal["low", "medium", "high", "undetermined"] | None = Field(
        description="AI 심각도 단계. 판단 보류면 `undetermined`입니다."
    )
    suspected_types: list[str] = Field(description="AI가 의심한 하자 유형 목록.")
    status: Literal["open", "accepted", "cancelled"] = Field(
        description="요청서 상태. `open`은 진행 중, `accepted`는 수락 완료, `cancelled`는 취소입니다."
    )
    accepted_proposal_id: UUID | None = Field(
        description="수락된 제안서 UUID. 수락 전이면 `null`입니다."
    )
    proposal_count: int = Field(description="요청서에 도착한 제안서 수(요청인 목록 기준).")
    my_proposal_id: UUID | None = Field(
        default=None, description="업체 목록에서 본인이 보낸 제안서 UUID. 없으면 `null`입니다."
    )
    my_proposal_status: Literal["pending", "accepted", "rejected"] | None = Field(
        default=None, description="업체 목록에서 본인 제안서 상태. 없으면 `null`입니다."
    )
    created_at: datetime = Field(description="요청서 생성 시각(UTC).")


class QuoteRequestDetailOut(QuoteRequestSummary):
    """견적 요청서 상세."""

    proposals: list[QuoteProposalOut] = Field(
        description="요청인은 도착한 모든 제안서, 업체는 본인 제안서만 반환합니다."
    )


class ProfileOut(BaseModel):
    """로그인한 사용자의 주거 프로필."""

    nickname: str = Field(description="서비스에서 표시할 닉네임.")
    role: Literal["requester", "provider"] = Field(
        description="계정 역할. 일반 사용자는 `requester`이며 클라이언트가 변경할 수 없습니다."
    )
    region_id: UUID = Field(description="거주 지역의 UUID.")
    address: str | None = Field(description="선택 등록 주소. 없으면 `null`입니다.")
    housing_type: HousingType = Field(description="거주 형태 코드.")
    provider_id: UUID | None = Field(
        description="연결된 업체 UUID. 업체 계정이면 본인 업체 ID, 요청인이면 `null`입니다."
    )


class ProfileUpsertRequest(BaseModel):
    """프로필 최초 등록·수정 요청."""

    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(
        min_length=1,
        max_length=80,
        description="닉네임. 공백만 입력할 수 없습니다.",
    )
    region_id: UUID = Field(description="`GET /regions`에서 확인한 거주 지역 UUID.")
    address: str | None = Field(
        default=None,
        description="선택 등록 주소. 없으면 생략하거나 `null`을 보냅니다.",
    )
    housing_type: HousingType = Field(
        description="거주 형태. `monthly_rent`, `jeonse`, `semi_jeonse`, `owned`, `other` 중 하나입니다."
    )

    @field_validator("nickname")
    @classmethod
    def nickname_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("닉네임은 공백일 수 없어요.")
        return value


class RegionOut(BaseModel):
    """프로필에서 선택할 수 있는 지역."""

    region_id: UUID = Field(description="지역 UUID.")
    name: str = Field(description="지역 식별 이름(예: `yongin`).")
    display_name: str = Field(description="화면에 표시할 지역 이름(시·군·구 포함).")
    parent_id: UUID | None = Field(
        default=None, description="상위 지역(시·도) UUID. 시·도 자체면 `null`입니다. 2단계 지역 선택에 씁니다."
    )


class RecordListItem(BaseModel):
    """내 정보의 하자 분석 기록 목록 항목."""

    record_id: UUID = Field(description="하자 기록의 UUID.")
    location: str | None = Field(description="하자 발견 위치(미입력 시 `null`).")
    material: str | None = Field(description="표면 재질(미입력 시 `null`).")
    symptoms: str | None = Field(description="증상 메모(미입력 시 `null`).")
    region_id: UUID | None = Field(
        description="분석 당시 저장한 지역 스냅샷 UUID. 없으면 `null`입니다."
    )
    region_name: str | None = Field(
        description="지역 표시명(예: 경기도 용인시). 지역이 없으면 `null`입니다."
    )
    suspected_types: list[str] = Field(
        description="저장된 진단의 의심 하자 유형 목록. 진단이 없으면 빈 배열입니다."
    )
    severity_score: int | None = Field(
        description="저장된 진단의 심각도 퍼센트. 진단이 없거나 판단 보류면 `null`입니다."
    )
    severity_level: Literal["low", "medium", "high", "undetermined"] | None = Field(
        description="저장된 진단의 심각도 단계. 진단이 없으면 `null`입니다."
    )
    created_at: datetime = Field(description="기록 생성 시각(UTC).")
    updated_at: datetime = Field(description="기록 마지막 수정 시각(UTC).")


class SupportProgramSummary(BaseModel):
    """소식지 목록·상세에 공통인 주거 지원 사업 정보."""

    id: UUID = Field(description="지원 사업의 고유 UUID.")
    title: str = Field(description="공고·사업 이름.")
    summary: str = Field(description="목록에 표시할 사업 목적 요약.")
    organization_name: str = Field(description="공고를 제공한 기관 또는 사업 주관기관.")
    region_scope: Literal["national", "local"] = Field(
        description="지원 범위. `national`은 전국, `local`은 특정 지역입니다."
    )
    region_name: str = Field(
        description="화면에 표시할 지역명. 전국 사업은 `전국`, 지역 사업은 시·군·구 표시명입니다."
    )
    target_housing_types: list[HousingType] = Field(
        description=(
            "공고 원문에서 확인된 거주 형태 태그. 신청 자격을 확정하는 값이 아니며, "
            "태그 일치 여부는 참고 정보입니다."
        )
    )
    deadline_text: str | None = Field(
        description="공식 원문의 신청기한 문구. 확인하지 못했으면 `null`입니다."
    )
    deadline_date: date | None = Field(
        description=(
            "명확히 해석한 마감일. 신청기한이 상시·기한 불명·복수 날짜 등이면 `null`입니다."
        )
    )
    deadline_kind: DeadlineKind = Field(
        description=(
            "신청기한 종류. `fixed`는 확정 날짜, `always_open`은 공식 상시·연중 신청, "
            "`unknown`은 기한 미확인 또는 모호한 문구입니다."
        )
    )
    is_closed: bool = Field(
        description=(
            "한국 시간 기준 마감일이 지난 확정 날짜 공고인지 여부. "
            "마감일 당일은 아직 마감이 아니며, 상시·기한 불명은 `false`입니다."
        )
    )
    detail_url: str = Field(description="공식 원문 또는 신청 페이지 URL(http/https).")
    source: SupportProgramSource = Field(
        description="데이터 출처. `seed`는 검증 시드, `gov24_api`는 보조금24 동기화입니다."
    )
    source_attribution: str = Field(description="화면과 문서에 표시할 출처 문구.")
    source_checked_at: datetime = Field(
        description="서버가 해당 공고의 출처를 마지막으로 확인한 시각(UTC)."
    )
    updated_at: datetime = Field(description="DB 행을 마지막으로 갱신한 시각(UTC).")


class SupportProgramListItem(SupportProgramSummary):
    """소식지 목록의 주거 지원 사업 항목."""

    housing_type_matched: bool = Field(
        description=(
            "로그인 사용자의 거주 형태가 공고 태그와 겹치는지 여부. "
            "신청 자격 충족을 확정하지 않습니다."
        )
    )


class SupportProgramListResponse(BaseModel):
    """소식지 목록 페이지 응답."""

    items: list[SupportProgramListItem] = Field(description="현재 페이지의 지원 사업 목록.")
    total: int = Field(description="필터(`status`)를 적용한 전체 지원 사업 수.")
    limit: int = Field(description="요청한 페이지 크기.")
    offset: int = Field(description="요청한 페이지 시작 위치.")
    has_more: bool = Field(description="다음 페이지가 남아 있는지 여부.")


class SupportProgramDetail(SupportProgramSummary):
    """주거 지원 사업 상세 조회 응답."""

    support_target: str = Field(description="공식 원문의 지원 대상·자격 설명.")
    support_content: str = Field(description="공식 원문의 지원 내용.")
    selection_criteria: str | None = Field(
        description="공식 원문의 선정 기준. 원문에 없으면 `null`입니다."
    )
    apply_method: str | None = Field(
        description="공식 원문의 신청 방법. 원문에 없으면 `null`입니다."
    )
    synced_at: datetime | None = Field(
        description="보조금24 API에서 마지막으로 동기화한 시각. 검증 시드는 `null`입니다."
    )


class RecordOut(BaseModel):
    """하자 기록 상세 조회 응답."""

    record_id: UUID = Field(description="하자 기록의 고유 UUID.")
    location: str | None = Field(
        description="사용자가 입력한 하자 발견 위치(미입력 시 `null`)."
    )
    material: str | None = Field(
        description="사용자가 입력한 표면 재질(미입력 시 `null`)."
    )
    symptoms: str | None = Field(
        description="사용자가 입력한 하자 증상 설명(미입력 시 `null`)."
    )
    region_id: UUID | None = Field(
        description="분석 당시 저장한 지역 스냅샷 UUID. 없으면 `null`입니다."
    )
    region_name: str | None = Field(
        description="지역 표시명(예: 경기도 용인시). 지역이 없으면 `null`입니다."
    )
    photo_observations: Any = Field(
        default=None,
        description="사진 분석으로 저장된 관찰 결과 JSON(원본 사진·좌표 미저장, 미분석 시 `null`).",
    )
    photos: list["SignedPhotoOut"] = Field(
        default_factory=list,
        description="비공개 Storage 사진의 단기 Signed URL 목록. Storage 미설정이면 빈 배열입니다.",
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


DraftKind = Literal["landlord", "provider"]
ChatSenderRole = Literal["requester", "provider"]
ChatMessageType = Literal["text", "record_summary"]


class DraftResponse(BaseModel):
    """점검·견적 요청문 생성 응답."""

    kind: DraftKind = Field(description="요청문 종류. `landlord` 또는 `provider`입니다.")
    text: str = Field(description="생성 또는 재사용된 요청문 본문(plain text).")
    input_revision: int = Field(description="요청문 생성에 사용한 기록 입력 버전.")
    diagnosis_generation: int = Field(description="요청문 생성에 사용한 진단 생성 번호.")


class DraftTemplateResponse(BaseModel):
    """모델 호출 없이 만든 요청문 기본 양식."""

    kind: DraftKind = Field(description="요청문 종류. `landlord` 또는 `provider`입니다.")
    text: str = Field(description="현재 기록의 확인된 사실을 채운 기본 양식 본문(plain text).")
    input_revision: int = Field(description="양식을 만든 시점의 기록 입력 버전.")
    diagnosis_generation: int | None = Field(
        description="양식에 반영한 진단 생성 번호. 진단이 없으면 `null`입니다."
    )


class WorkTypeOut(BaseModel):
    """업체 검색에 사용하는 작업 종류."""

    work_type_id: UUID = Field(description="작업 종류 UUID.")
    name: str = Field(description="화면에 표시할 작업 이름(예: `곰팡이 제거`).")


class ProviderOut(BaseModel):
    """업체 검색 결과의 업체 후보."""

    provider_id: UUID = Field(description="업체 UUID. 샘플 후보는 고정 시연용 UUID입니다.")
    name: str = Field(description="업체명.")
    phone: str | None = Field(
        description="공개 전화번호. 샘플 후보처럼 확인된 연락처가 없으면 `null`입니다."
    )
    rating: float = Field(description="평균 평점(0.0~5.0). 리뷰가 없으면 `0.0`입니다.")
    review_count: int = Field(description="등록된 리뷰 수.")
    description: str | None = Field(
        description="업체 소개·시공 강점. 확인된 소개가 없으면 `null`입니다."
    )
    specialty_work_types: list[WorkTypeOut] = Field(
        description="업체의 전체 특화 분야 목록. 없으면 빈 배열입니다."
    )
    region_names: list[str] = Field(
        default_factory=list,
        description="업체 출장 지역 표시명 목록. 업체 제안서에서 채우며, 없으면 빈 배열입니다.",
    )
    chat_available: bool = Field(
        description="사전 등록된 업체 계정이 연결되어 앱 내 채팅이 가능한지 여부. 샘플은 항상 `false`입니다."
    )
    is_sample: bool = Field(
        description="실제 후보가 없을 때 반환한 시연용 샘플 후보인지 여부."
    )


class ProviderSearchResponse(BaseModel):
    """업체 검색 응답."""

    providers: list[ProviderOut] = Field(
        description="지역과 선택한 특화 분야에 맞는 업체 후보 목록. 별점 내림차순입니다."
    )
    is_sample: bool = Field(
        description="후보 전체가 시연용 샘플인지 여부. 실제 후보가 하나라도 있으면 `false`입니다."
    )


class ProviderDetailOut(BaseModel):
    """업체 상세 정보."""

    provider_id: UUID = Field(description="업체 UUID.")
    name: str = Field(description="업체명.")
    phone: str | None = Field(description="공개 전화번호. 없으면 `null`입니다.")
    rating: float = Field(description="평균 평점(0.0~5.0). 리뷰가 없으면 `0.0`입니다.")
    review_count: int = Field(description="등록된 리뷰 수.")
    description: str | None = Field(description="업체 소개·시공 강점. 없으면 `null`입니다.")
    address: str | None = Field(description="사업장 주소 또는 활동 거점. 없으면 `null`입니다.")
    business_hours: str | None = Field(description="영업시간 안내. 없으면 `null`입니다.")
    career_years: int | None = Field(description="경력 연수. 확인되지 않았으면 `null`입니다.")
    chat_available: bool = Field(
        description="사전 등록된 업체 계정이 연결되어 앱 내 채팅이 가능한지 여부."
    )
    regions: list[RegionOut] = Field(description="출장 가능 지역 목록.")
    work_types: list[WorkTypeOut] = Field(description="특화 분야 목록.")
    is_sample: Literal[False] = Field(
        default=False, description="상세 API는 실제 업체만 반환하므로 항상 `false`입니다."
    )


class ChatRoomCreateRequest(BaseModel):
    """채팅방 생성·재사용 요청."""

    model_config = ConfigDict(extra="forbid")

    provider_id: UUID = Field(description="채팅할 실제 업체의 UUID(`GET /providers`).")
    record_id: UUID | None = Field(
        default=None,
        description="같이 공유할 본인 하자 기록 UUID. 생략하면 방만 만들거나 재사용합니다.",
    )


class ChatRoomOut(BaseModel):
    """채팅방 정보."""

    room_id: UUID = Field(description="채팅방 UUID.")
    requester_id: UUID = Field(description="요청인(기록 소유자) 사용자 UUID.")
    provider_id: UUID = Field(description="업체 UUID.")
    provider_name: str = Field(description="업체명.")
    latest_record_id: UUID | None = Field(
        description="가장 최근에 공유한 하자 기록 UUID. 공유한 기록이 없으면 `null`입니다."
    )
    last_message_at: datetime | None = Field(
        description="마지막 메시지 시각(UTC). 메시지가 없으면 `null`입니다."
    )
    created_at: datetime = Field(description="채팅방 생성 시각(UTC).")
    updated_at: datetime = Field(description="채팅방 마지막 갱신 시각(UTC).")


class ChatRoomListItem(ChatRoomOut):
    """채팅 목록의 채팅방 항목."""

    counterpart_name: str = Field(
        description="상대방 표시 이름. 업체에게는 요청인 닉네임(프로필이 없으면 `요청인`)입니다."
    )
    last_message_preview: str | None = Field(
        description="최근 메시지 본문 앞 80자. 메시지가 없으면 `null`입니다."
    )
    unread_count: int = Field(
        description="내가 아직 읽지 않은 상대방 메시지 수. 본인이 보낸 메시지는 세지 않습니다."
    )


class ChatReadReceipt(BaseModel):
    """채팅방 읽음 처리 결과."""

    room_id: UUID = Field(description="읽음 처리한 채팅방 UUID.")
    last_read_at: datetime = Field(
        description="서버가 기록한 읽음 시각(UTC). 이후 도착한 상대방 메시지는 미읽음으로 셉니다."
    )
    unread_count: int = Field(
        description="읽음 처리 직후 남은 상대방 메시지 수. 동시에 도착한 메시지가 있으면 0보다 클 수 있습니다."
    )


class ChatMessageCreateRequest(BaseModel):
    """채팅 메시지 전송 요청."""

    model_config = ConfigDict(extra="forbid")

    client_message_id: UUID = Field(
        description="클라이언트가 생성한 메시지 고유 UUID(재전송 멱등성 식별자)."
    )
    content: str = Field(
        min_length=1,
        max_length=2000,
        description="메시지 본문. 공백만 입력할 수 없으며 최대 2000자입니다.",
    )

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("메시지는 공백일 수 없어요.")
        return value


class ChatMessageOut(BaseModel):
    """저장된 채팅 메시지."""

    message_id: UUID = Field(description="메시지 UUID.")
    room_id: UUID = Field(description="메시지가 속한 채팅방 UUID.")
    sender_id: UUID = Field(description="발신자 사용자 UUID(토큰에서 결정).")
    sender_role: ChatSenderRole = Field(
        description="발신자 역할. 요청인은 `requester`, 연결된 업체 계정은 `provider`입니다."
    )
    message_type: ChatMessageType = Field(
        description="메시지 종류. 일반 텍스트는 `text`, 하자 분석 요약은 `record_summary`입니다."
    )
    record_id: UUID | None = Field(
        description="`record_summary` 메시지가 연결된 하자 기록 UUID. 텍스트 메시지는 `null`입니다."
    )
    content: str = Field(description="메시지 본문.")
    payload: Any = Field(
        default=None,
        description="`record_summary` 메시지의 구조화 요약(하자 입력·진단 결과). 텍스트 메시지는 `null`입니다.",
    )
    client_message_id: UUID = Field(
        description="재전송 멱등성 식별 UUID. 서버가 만든 요약 메시지는 서버 발급 UUID입니다."
    )
    created_at: datetime = Field(description="메시지 생성 시각(UTC).")


class ChatMessageListResponse(BaseModel):
    """채팅 메시지 이력 페이지."""

    messages: list[ChatMessageOut] = Field(
        description="`created_at`, `id` 오름차순으로 정렬된 메시지 목록."
    )
    limit: int = Field(description="요청한 페이지 크기.")
    offset: int = Field(description="요청한 건너뛸 메시지 수.")
    has_more: bool = Field(description="다음 페이지가 남아 있는지 여부.")


QuoteProposalOut.model_rebuild()
RecordOut.model_rebuild()
