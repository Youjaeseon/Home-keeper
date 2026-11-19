import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from scalar_fastapi import add_scalar_reference
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import ApiError
from app.records import router as records_router
from app.schemas import HealthResponse

logger = logging.getLogger("career_pair_api")

_API_DESCRIPTION = """
임차 주택 하자 대응을 위한 하자 기록과 대화 메시지를 관리하는 MVP 백엔드 API입니다.

### 인증과 소유권
- `GET /health`를 제외한 모든 `/records` 엔드포인트는 `Authorization: Bearer <access_token>` 헤더(Supabase Auth JWT)가 필요합니다.
- 토큰의 `sub` 클레임(UUID)이 요청 사용자로 식별되며, 본인이 소유한 하자 기록에만 접근할 수 있습니다. 다른 사용자의 기록이나 존재하지 않는 리소스는 `404`로 응답합니다.

### 입력 버전(`input_revision`) 낙관적 동시성
- 새 하자 기록의 `input_revision`은 `0`에서 시작합니다.
- 위치·증상 변경, 사용자 메시지 추가, 과거 사용자 메시지 내용 변경처럼 실제 입력이 바뀔 때만 `1`씩 증가합니다.
- `POST /records/{record_id}/messages`와 `PUT /records/{record_id}/messages/{message_id}`는 요청 본문에 `input_revision`이 필요하며, 서버 최신 버전과 다르면 `409 Conflict`(`revision_conflict`)와 현재 `input_revision`을 반환합니다.

### 공통 오류 형식
- 모든 오류는 `{ "code": string, "message": string, "input_revision"?: number }` 형식으로 반환됩니다.
""".strip()

_OPENAPI_TAGS = [
    {
        "name": "records",
        "description": "하자 기록 생성·조회·수정 및 사용자 대화 메시지 저장·편집 API. 모든 요청에 Supabase Auth Bearer JWT 인증과 기록 소유권 검증이 필요합니다.",
    },
    {
        "name": "health",
        "description": "서버 상태 확인용 엔드포인트(인증 불필요).",
    },
]

app = FastAPI(
    title="Career Pair API",
    version="0.1.0",
    description=_API_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
)
app.include_router(records_router)
add_scalar_reference(app, route="/docs")


def _error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, **extra},
    )


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    extra = {}
    if exc.input_revision is not None:
        extra["input_revision"] = exc.input_revision
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, **extra},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, __: RequestValidationError):
    return _error(422, "invalid_request", "요청 형식이 올바르지 않습니다.")


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return _error(404, "not_found", "요청한 경로를 찾을 수 없습니다.")
    if exc.status_code == 405:
        return _error(405, "method_not_allowed", "허용되지 않은 메서드입니다.")
    return _error(exc.status_code, "http_error", "요청을 처리하지 못했습니다.")


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception):
    # Logs the traceback only; request bodies, tokens, and headers are never logged.
    logger.error(
        "unhandled error", exc_info=(type(exc), exc, exc.__traceback__)
    )
    return _error(500, "internal_error", "요청을 처리하지 못했습니다.")


@app.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    summary="서버 상태 확인",
    description="API 서버가 정상적으로 기동되어 요청을 받을 수 있는지 확인합니다. 인증 헤더 없이 호출할 수 있으며, 데이터베이스 연결 여부는 검사하지 않습니다.",
    response_description="서버 정상 응답",
)
def health():
    return {"status": "ok"}
