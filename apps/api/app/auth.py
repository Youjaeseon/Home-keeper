from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.errors import ApiError

_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description=(
        "Supabase Auth에서 발급한 JWT 액세스 토큰을 "
        "`Authorization: Bearer <access_token>` 헤더로 전달합니다. "
        "검증된 토큰의 `sub` 클레임(UUID)이 하자 기록 소유자로 사용됩니다."
    ),
)


class _InvalidToken(Exception):
    pass


class TokenVerifier:
    def __init__(self, settings: Settings):
        self._secret = settings.supabase_jwt_secret
        self._audience = settings.supabase_jwt_audience
        self._issuer = settings.supabase_jwt_issuer
        self._jwks = None
        self._jwks_uri = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

    def _signing_key(self, token: str):
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
        except jwt.InvalidTokenError as exc:
            raise _InvalidToken from exc

        if algorithm == "HS256":
            if not self._secret:
                raise _InvalidToken
            return algorithm, self._secret

        if algorithm not in {"RS256", "ES256"}:
            raise _InvalidToken

        if self._jwks is None:
            self._jwks = jwt.PyJWKClient(self._jwks_uri, cache_keys=True)
        try:
            return algorithm, self._jwks.get_signing_key_from_jwt(token).key
        except Exception as exc:  # JWKS fetch/parse failures must fail closed.
            raise _InvalidToken from exc

    def verify(self, token: str) -> UUID:
        algorithm, key = self._signing_key(token)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
            return UUID(str(claims["sub"]))
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            raise _InvalidToken from exc


@lru_cache(maxsize=1)
def _verifier() -> TokenVerifier:
    return TokenVerifier(get_settings())


def verify_access_token(token: str) -> UUID | None:
    """Return the token subject, or None when the token is invalid or expired."""
    try:
        return _verifier().verify(token)
    except _InvalidToken:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    user_id = verify_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthorized()
    return user_id


def _unauthorized() -> ApiError:
    return ApiError(
        401,
        "unauthorized",
        "액세스 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
