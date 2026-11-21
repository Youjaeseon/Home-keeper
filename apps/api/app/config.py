import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    supabase_url: str
    supabase_jwt_secret: str | None
    supabase_jwt_audience: str
    supabase_jwt_issuer: str
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: float
    yolo_model_path: str | None = None
    model_api_key: str | None = None
    sam_timeout_seconds: float = 30


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    supabase_url = _required("SUPABASE_URL").rstrip("/")
    return Settings(
        database_url=_required("DATABASE_URL"),
        supabase_url=supabase_url,
        supabase_jwt_secret=os.environ.get("SUPABASE_JWT_SECRET") or None,
        supabase_jwt_audience=os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated"),
        supabase_jwt_issuer=os.environ.get("SUPABASE_JWT_ISSUER") or f"{supabase_url}/auth/v1",
        llm_api_key=os.environ.get("LLM_API_KEY") or None,
        llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "20")),
        yolo_model_path=os.environ.get("YOLO_MODEL_PATH") or None,
        model_api_key=os.environ.get("MODEL_API_KEY") or None,
        sam_timeout_seconds=float(os.environ.get("SAM_TIMEOUT_SECONDS", "30")),
    )
