import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from scalar_fastapi import add_scalar_reference
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import ApiError
from app.profile import router as profile_router
from app.records import router as records_router
from app.schemas import HealthResponse
from app.support_programs import router as support_programs_router

logger = logging.getLogger("career_pair_api")

_API_DESCRIPTION = """
임차 주택 하자 대응을 위한 하자 기록과 대화 메시지를 관리하는 MVP 백엔드 API입니다.

### 인증과 소유권
- `GET /health`를 제외한 `/records`, `/me/profile`, `/regions`, `/support-programs` 엔드포인트는 `Authorization: Bearer <access_token>` 헤더(Supabase Auth JWT)가 필요합니다.
- 토큰의 `sub` 클레임(UUID)이 요청 사용자로 식별되며, 본인이 소유한 하자 기록에만 접근할 수 있습니다. 다른 사용자의 기록이나 존재하지 않는 리소스는 `404`로 응답합니다.

### 프로필과 내 기록
- `GET`·`PUT /me/profile`은 검증된 사용자 ID로 본인 프로필만 조회·저장합니다. 새 프로필의 역할은 서버가 `requester`로 정하며 요청에서 역할을 바꿀 수 없습니다.
- `GET /regions`는 프로필의 거주 지역 선택에 사용할 지역 목록을 반환합니다.
- `GET /records`는 본인 소유 기록을 최근 수정 순으로 요약해 반환합니다. 다른 사용자의 기록은 포함하지 않습니다.

### 주거 지원 사업 소식지
- `GET /support-programs`는 로그인 사용자의 프로필 지역·상위 지역·전국 공고를 반환합니다. 거주 형태 태그가 일치하는 공고를 우선 표시하며, 태그 일치는 신청 자격을 확정하지 않습니다.
- 마감일이 확정된 공고는 한국 시간 기준 마감일 다음 날부터 `is_closed=true`가 되고 목록 하단에 배치됩니다. 상시·기한 불명은 `deadline_kind`로 구분합니다.
- `GET /support-programs/{program_id}`는 공식 원문 링크, 지원 대상·내용·신청 방법, 출처와 출처 확인 시점을 반환합니다.

### 입력 버전(`input_revision`) 낙관적 동시성
- 새 하자 기록의 `input_revision`은 `0`에서 시작합니다.
- 위치·증상 변경, 사용자 메시지 추가, 과거 사용자 메시지 내용 변경처럼 실제 입력이 바뀔 때만 `1`씩 증가합니다.
- `POST /records/{record_id}/messages`와 `PUT /records/{record_id}/messages/{message_id}`는 요청 본문에 `input_revision`이 필요하며, 서버 최신 버전과 다르면 `409 Conflict`(`revision_conflict`)와 현재 `input_revision`을 반환합니다.

### 시연용 다음 질문
- `POST /records/{record_id}/next-question`은 현재 저장된 입력과 대화로 다음 질문을 결정하며, 같은 `input_revision`의 저장 결과는 재생성하지 않고 반환합니다.
- 실제 LLM이 아니라 곰팡이 의심 창가 얼룩 사례의 두 질문을 사용하는 샘플 규칙이며, 응답의 `source`는 항상 `sample`입니다.

### 사진·위치·재질 일괄 분석
- `POST /records/{record_id}/analyze`는 사진 1~2장과 위치·재질·증상·외부 분석 동의를 multipart로 받아 샘플 진단을 저장합니다.
- 현재는 실제 사진 분석이나 LLM을 호출하지 않으며, `photo_analysis.applied=false`, `detections=[]`, `source=sample`로 실제 분석이 아님을 표시합니다.

### 공통 오류 형식
- 모든 오류는 `{ "code": string, "message": string, "input_revision"?: number }` 형식으로 반환됩니다.
""".strip()

_OPENAPI_TAGS = [
    {
        "name": "records",
        "description": "하자 기록 생성·목록·조회·수정, 사진·위치·재질 일괄 분석, 사용자 대화 메시지 저장·편집, 시연용 다음 질문 조회 API. 모든 요청에 Supabase Auth Bearer JWT 인증과 기록 소유권 검증이 필요합니다.",
    },
    {
        "name": "profile",
        "description": "로그인 사용자의 주거 프로필 조회·등록·수정과 지역 목록 조회 API. 역할은 서버가 정하며 클라이언트가 변경할 수 없습니다.",
    },
    {
        "name": "support-programs",
        "description": "프로필 지역·상위 지역·전국 주거 지원 사업 소식지 API. 출처 확인 시점과 마감 종류를 함께 제공하며, 공고 데이터를 클라이언트가 수정하는 API는 없습니다.",
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
app.include_router(profile_router)
app.include_router(support_programs_router)
add_scalar_reference(app, route="/docs")


_original_openapi = app.openapi


def _openapi_with_multipart_descriptions():
    if app.openapi_schema:
        return app.openapi_schema
    schema = _original_openapi()
    for name, component in schema.get("components", {}).get("schemas", {}).items():
        if name.startswith("Body_") and not component.get("description"):
            component["description"] = (
                "사진과 위치·재질·증상, 외부 분석 동의를 multipart/form-data로 전송하는 요청 본문입니다."
            )
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_multipart_descriptions


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
