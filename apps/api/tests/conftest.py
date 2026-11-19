import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql://localhost:5432/postgres"
)
DB_NAME = os.environ.get("TEST_DATABASE_NAME", "career_pair_test")
if not re.fullmatch(r"[a-z_][a-z0-9_]*_test", DB_NAME):
    raise RuntimeError("TEST_DATABASE_NAME must end in _test and contain only [a-z0-9_]")

_parts = urlsplit(ADMIN_URL)
TEST_ADMIN_URL = _parts._replace(path=f"/{DB_NAME}").geturl()
RUNTIME_PASSWORD = "career_pair_test_only"
RUNTIME_URL = (
    f"postgresql://career_pair_runtime:{RUNTIME_PASSWORD}"
    f"@{_parts.hostname or 'localhost'}:{_parts.port or 5432}/{DB_NAME}"
)

TEST_JWT_SECRET = "test-only-supabase-jwt-secret-with-enough-length"
SUPABASE_URL = "http://127.0.0.1:54321"
ISSUER = f"{SUPABASE_URL}/auth/v1"

os.environ["DATABASE_URL"] = RUNTIME_URL
os.environ["SUPABASE_URL"] = SUPABASE_URL
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["SUPABASE_JWT_AUDIENCE"] = "authenticated"
os.environ.pop("SUPABASE_JWT_ISSUER", None)


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.migrate import apply_migrations

    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{DB_NAME}"')

    apply_migrations(TEST_ADMIN_URL)

    with psycopg.connect(TEST_ADMIN_URL, autocommit=True) as conn:
        conn.execute(
            f"ALTER ROLE career_pair_runtime LOGIN PASSWORD '{RUNTIME_PASSWORD}'"
        )
    yield


@pytest.fixture
def admin():
    with psycopg.connect(
        TEST_ADMIN_URL, autocommit=True, row_factory=dict_row
    ) as conn:
        yield conn


@pytest.fixture
def user_factory(admin):
    def create() -> object:
        user_id = uuid4()
        admin.execute("INSERT INTO auth.users (id) VALUES (%s)", (user_id,))
        return user_id

    return create


@pytest.fixture
def token_for():
    def create(
        user_id,
        *,
        secret=TEST_JWT_SECRET,
        audience="authenticated",
        issuer=ISSUER,
        expires_in=300,
    ) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": str(user_id),
                "aud": audience,
                "iss": issuer,
                "iat": now,
                "exp": now + timedelta(seconds=expires_in),
                "role": "authenticated",
            },
            secret,
            algorithm="HS256",
        )

    return create


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def record_factory(client, token_for):
    def create(user_id):
        response = client.post(
            "/records",
            headers={"Authorization": f"Bearer {token_for(user_id)}"},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def question_factory(admin):
    def create(record_id, content, options=None, *, answered=False):
        with admin.transaction():
            record = admin.execute(
                """
                SELECT input_revision, conversation_sequence
                FROM records WHERE id = %s FOR UPDATE
                """,
                (record_id,),
            ).fetchone()
            sequence = record["conversation_sequence"] + 1
            question_id = uuid4()
            admin.execute(
                """
                INSERT INTO questions
                    (id, record_id, sequence, content, options, answered, input_revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    question_id,
                    record_id,
                    sequence,
                    content,
                    Jsonb(options or []),
                    answered,
                    record["input_revision"],
                ),
            )
            admin.execute(
                "UPDATE records SET conversation_sequence = %s WHERE id = %s",
                (sequence, record_id),
            )
        return question_id

    return create


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
