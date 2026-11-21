import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from scalar_fastapi import add_scalar_reference
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.chat import router as chat_router
from app.diagnosis import router as diagnosis_router
from app.drafts import router as drafts_router
from app.docs_auth import router as docs_auth_router
from app.errors import ApiError
from app.profile import router as profile_router
from app.providers import router as providers_router
from app.records import router as records_router
from app.schemas import HealthResponse
from app.support_programs import router as support_programs_router

logger = logging.getLogger("career_pair_api")

_API_DESCRIPTION = """
임차 주택 하자 대응을 위한 하자 기록과 대화 메시지를 관리하는 MVP 백엔드 API입니다.

### 인증과 소유권
- Scalar의 Authentication에서 `SupabaseLogin`을 선택하고 Username(이메일)·Password를 입력해 토큰을 발급받으면 요청에 자동 적용됩니다. Client ID·Client Secret은 비워 둡니다. 기존 `HTTPBearer` 토큰 직접 입력도 가능합니다.
- `GET /health`를 제외한 `/records`, `/me/profile`, `/regions`, `/support-programs`, `/chat` 등 엔드포인트는 `Authorization: Bearer <access_token>` 헤더(Supabase Auth JWT)가 필요합니다. `/chat/ws`는 헤더 또는 `access_token` 쿼리를 받습니다.
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

### 사진 관찰과 AI 진단
- `POST /records/{record_id}/analyze`는 사진 1~2장과 위치·재질·증상·외부 분석 동의를 multipart로 받아 사진 관찰과 구조화 진단을 저장합니다.
- `YOLO_MODEL_PATH` 설정 시 실제 사진 탐지를 수행하고, 동의·키가 있으면 Meta SAM 3.1로 분할해 화면 점유 비율을 계산합니다. YOLO가 읽지 못한 사진만 비전 LLM이 독립 관찰합니다. 두 모델 경로가 모두 미설정이면 샘플 모드입니다.
- `POST /records/{record_id}/diagnosis`는 저장된 사진 관찰과 현재 입력으로 진단을 생성하거나, 입력 버전이 같은 기존 진단을 재사용합니다. `regenerate=true`면 다시 생성합니다.

### 점검·견적 요청문
- `POST /records/{record_id}/drafts/{kind}`는 저장된 입력과 진단으로 `landlord`(임대인 점검) 또는 `provider`(업체 견적) 요청문을 생성합니다. 입력 버전과 진단 생성 번호가 모두 같은 기존 요청문은 재사용하며, `regenerate=true`일 때만 모델을 다시 호출합니다.
- 생성 중 입력·진단이 바뀌면 `409`로 저장을 거부하고, 모델 실패 시 기존 요청문을 유지합니다. 모델 키 미설정은 `503`, 호출 실패는 `502`, 제한 시간 초과는 `504`입니다.
- `GET /records/{record_id}/drafts/{kind}/template`은 모델 호출 없이 확인된 사실을 채운 기본 양식을 반환합니다. 진단이 없어도 사용할 수 있습니다.

### 업체 검색과 1:1 채팅
- `GET /work-types`, `GET /providers`는 지역과 작업이 모두 일치하는 실제 업체를 찾고, 실제 후보가 없을 때만 `is_sample=true` 샘플 후보를 반환합니다. `chat_available`은 사전 등록된 업체 계정 연결 여부입니다.
- `POST /chat/rooms`는 요청인–업체 방을 만들거나 재사용하며, `record_id`를 보내면 서버가 만든 하자 요약을 공유합니다. `GET/POST /chat/rooms/{room_id}/messages`는 참여자만 접근할 수 있고 `client_message_id`로 재전송을 멱등 처리합니다.
- `GET /chat/rooms`는 방별 `unread_count`를 포함합니다. `POST /chat/rooms/{room_id}/read`가 서버 시각으로 읽음 상태를 저장하며 본인이 보낸 메시지는 미읽음으로 세지 않습니다.
- 실시간 수신은 `ws://<API>/chat/ws` WebSocket으로 제공합니다. `Authorization: Bearer` 헤더 또는 `access_token` 쿼리로 인증하고, 저장된 메시지는 참여자에게 `{"type":"message","room_id":"...","message":{...}}` 이벤트로 전달됩니다. 재연결 후에는 REST 이력으로 놓친 메시지를 맞춥니다.

### 공통 오류 형식
- 모든 오류는 `{ "code": string, "message": string, "input_revision"?: number }` 형식으로 반환됩니다.
""".strip()

_OPENAPI_TAGS = [
    {
        "name": "records",
        "description": "하자 기록 생성·목록·조회·수정, 사진·위치·재질 일괄 분석, 사용자 대화 메시지 저장·편집, 시연용 다음 질문 조회 API. 모든 요청에 Supabase Auth Bearer JWT 인증과 기록 소유권 검증이 필요합니다.",
    },
    {
        "name": "diagnosis",
        "description": "저장된 사진 관찰과 입력값으로 구조화 진단을 생성·재생성하고, 입력 버전이 같은 기존 진단을 재사용하는 API. 본인 기록만 사용합니다.",
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
        "name": "drafts",
        "description": "임대인 점검·업체 견적 요청문 생성과 모델 호출 없는 기본 양식 API. 본인 기록만 사용하며 편집본 저장 API는 없습니다.",
    },
    {
        "name": "providers",
        "description": "업체 검색용 작업 종류·지역 필터와 채팅 가능 여부를 포함한 업체 후보 조회 API.",
    },
    {
        "name": "chat",
        "description": "요청인–업체 1:1 채팅방 목록·생성·재사용, 하자 요약 공유, 메시지 이력·전송, 방별 미읽음 수·읽음 처리 API. 참여자만 접근하며 실시간 수신은 인증된 WebSocket으로 제공합니다.",
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
app.include_router(diagnosis_router)
app.include_router(profile_router)
app.include_router(support_programs_router)
app.include_router(drafts_router)
app.include_router(providers_router)
app.include_router(chat_router)
app.include_router(docs_auth_router)
add_scalar_reference(
    app, route="/docs", authentication={"preferredSecurityScheme": "SupabaseLogin"}
)


_original_openapi = app.openapi


def _openapi_with_multipart_descriptions():
    if app.openapi_schema:
        return app.openapi_schema
    schema = _original_openapi()
    schema["components"]["securitySchemes"]["SupabaseLogin"] = {
        "type": "oauth2",
        "description": "Username에 Supabase 계정 이메일을 입력하고 로그인하세요. Client ID와 Client Secret은 비워 둡니다.",
        "flows": {"password": {"tokenUrl": "/auth/token", "scopes": {}}},
    }
    for path in schema["paths"].values():
        for operation in path.values():
            if isinstance(operation, dict) and {"HTTPBearer": []} in operation.get("security", []):
                operation["security"].insert(0, {"SupabaseLogin": []})
    for name, component in schema.get("components", {}).get("schemas", {}).items():
        if name.startswith("Body_") and not component.get("description"):
            component["description"] = (
                "사진과 위치·재질·증상, 외부 분석 동의를 multipart/form-data로 전송하는 요청 본문입니다."
            )
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_multipart_descriptions


@app.get("/vision-test", include_in_schema=False)
def vision_test():
    return FileResponse(
        Path(__file__).with_name("vision-test.html"),
        headers={"Cache-Control": "no-store"},
    )


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
