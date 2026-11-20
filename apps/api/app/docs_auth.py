import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


@router.post("/auth/token", include_in_schema=False)
async def docs_token(
    username: Annotated[str, Form(min_length=1)],
    password: Annotated[str, Form(min_length=1)],
    grant_type: Annotated[str, Form()] = "password",
):
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}

    def error(status: int, code: str, description: str):
        return JSONResponse(
            status_code=status,
            content={"error": code, "error_description": description},
            headers=headers,
        )

    if grant_type != "password":
        return error(400, "unsupported_grant_type", "이메일·비밀번호 로그인을 사용해 주세요.")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not key:
        return error(503, "temporarily_unavailable", "SUPABASE_PUBLISHABLE_KEY 설정이 필요합니다.")
    url = get_settings().supabase_url
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": key},
                json={"email": username.strip(), "password": password},
            )
    except httpx.RequestError:
        return error(502, "temporarily_unavailable", "인증 서버에 연결할 수 없습니다.")
    if response.status_code == 429:
        return error(429, "temporarily_unavailable", "로그인 요청이 많습니다. 잠시 후 다시 시도해 주세요.")
    if response.status_code in {400, 401, 403, 422}:
        return error(400, "invalid_grant", "로그인 정보를 확인해 주세요. 이메일 인증 또는 MFA가 필요할 수 있습니다.")
    if not response.is_success:
        return error(502, "temporarily_unavailable", "인증 서버 요청에 실패했습니다.")
    try:
        token = TokenResponse.model_validate(response.json())
    except ValueError:
        return error(502, "temporarily_unavailable", "인증 서버 응답을 확인할 수 없습니다.")
    return JSONResponse(content=token.model_dump(), headers=headers)
