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
    )
