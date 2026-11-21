class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        input_revision: int | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.input_revision = input_revision
        self.headers = headers


def not_found(message: str = "기록을 찾을 수 없습니다.") -> ApiError:
    return ApiError(404, "not_found", message)


def revision_conflict(current: int) -> ApiError:
    return ApiError(
        409,
        "revision_conflict",
        "입력이 변경되었습니다. 최신 기록을 확인한 뒤 다시 시도해 주십시오.",
        input_revision=current,
    )


def message_conflict(current: int) -> ApiError:
    return ApiError(
        409,
        "message_conflict",
        "같은 메시지 ID로 다른 내용이 이미 저장되었습니다.",
        input_revision=current,
    )


def invalid_request(message: str) -> ApiError:
    return ApiError(422, "invalid_request", message)


def diagnosis_conflict(current: int) -> ApiError:
    return ApiError(
        409,
        "diagnosis_conflict",
        "진단이 교체되어 요청문을 저장하지 않았습니다. 다시 생성해 주세요.",
        input_revision=current,
    )


def llm_unavailable() -> ApiError:
    return ApiError(
        503,
        "llm_unavailable",
        "요청문 생성 모델이 설정되지 않았습니다. 기본 양식을 사용해 주세요.",
    )


def llm_failed() -> ApiError:
    return ApiError(
        502,
        "llm_error",
        "요청문 생성에 실패했습니다. 다시 시도하거나 기본 양식을 사용해 주세요.",
    )


def llm_timeout() -> ApiError:
    return ApiError(
        504,
        "llm_timeout",
        "요청문 생성 응답이 지연되고 있습니다. 다시 시도하거나 기본 양식을 사용해 주세요.",
    )


def diagnosis_llm_unavailable() -> ApiError:
    return ApiError(
        503,
        "llm_unavailable",
        "진단 모델이 설정되지 않았습니다. 서버에 LLM_API_KEY를 설정해 주세요.",
    )


def diagnosis_llm_failed() -> ApiError:
    return ApiError(
        502,
        "llm_error",
        "진단 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    )


def diagnosis_llm_timeout() -> ApiError:
    return ApiError(
        504,
        "llm_timeout",
        "진단 생성 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
    )


def chat_message_conflict() -> ApiError:
    return ApiError(
        409,
        "message_conflict",
        "같은 메시지 ID로 다른 내용이 이미 저장되었습니다.",
    )
