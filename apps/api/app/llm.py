"""Minimal server-side LLM client for draft generation (OpenAI-compatible Chat Completions).

Endpoint and payload follow the official reference:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
Prompts, model responses, and request bodies are never logged.
"""

import httpx

from app.config import get_settings

MAX_OUTPUT_CHARS = 4000

SYSTEM_PROMPT = """\
너는 임차 주택 하자 기록을 바탕으로 점검·견적 요청문 초안을 작성하는 도우미다.
- 주어진 입력만 사용하고 업체명, 연락처, 주소, 금액, 방문 일정 같은 새로운 사실을 만들지 않는다.
- '확인된 내용', '추정 원인(확인 필요)', '추가 확인이 필요한 사항'을 구분해 쓴다.
- 추정 원인은 '가능성', '확인 필요'처럼 단정하지 않는 표현만 사용한다.
- 마크다운과 이모지 없이 plain text로, 800자 안팎으로 쓴다.
- 요청문 본문만 출력하고 설명이나 인사말을 덧붙이지 않는다.
"""


class LlmUnavailable(Exception):
    """LLM_API_KEY is not configured."""


class LlmError(Exception):
    """Upstream call failed or returned an unusable response."""


class LlmTimeout(LlmError):
    """Upstream call exceeded the configured timeout."""


def generate_text(prompt: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise LlmUnavailable

    try:
        response = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=settings.llm_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise LlmTimeout from exc
    except httpx.HTTPError as exc:
        raise LlmError from exc

    if response.status_code >= 400:
        raise LlmError

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LlmError from exc

    if not isinstance(content, str):
        raise LlmError
    content = content.strip()
    if not content:
        raise LlmError
    if len(content) > MAX_OUTPUT_CHARS:
        raise LlmError
    return content
