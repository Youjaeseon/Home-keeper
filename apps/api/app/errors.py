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
