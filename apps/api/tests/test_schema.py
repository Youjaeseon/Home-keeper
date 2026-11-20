import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

APP_TABLES = {
    "records",
    "questions",
    "messages",
    "providers",
    "regions",
    "work_types",
    "provider_regions",
    "provider_work_types",
}


def _new_record(admin) -> tuple[object, object]:
    owner_id = uuid4()
    record_id = uuid4()
    admin.execute("INSERT INTO auth.users (id) VALUES (%s)", (owner_id,))
    admin.execute(
        "INSERT INTO records (id, owner_id) VALUES (%s, %s)",
        (record_id, owner_id),
    )
    return owner_id, record_id


def test_all_agreed_tables_exist(admin):
    rows = admin.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    ).fetchall()
    assert APP_TABLES <= {row["table_name"] for row in rows}


def test_initial_migration_is_recorded(admin):
    versions = {
        row["version"]
        for row in admin.execute("SELECT version FROM schema_migrations").fetchall()
    }
    assert "001_init.sql" in versions
    assert "002_message_submission.sql" in versions
    assert "003_backend_rls.sql" in versions
    assert "004_protect_rls_trigger.sql" in versions
    assert "005_next_question_grants.sql" in versions
    assert "006_records_material.sql" in versions


def test_records_material_column(admin):
    column = admin.execute(
        """
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'records'
          AND column_name = 'material'
        """
    ).fetchone()
    assert column == {"data_type": "text", "is_nullable": "YES"}


def test_public_tables_have_rls_for_backend_only(admin):
    rows = admin.execute(
        "SELECT relname, relrowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
    ).fetchall()
    assert APP_TABLES | {"schema_migrations"} <= {row["relname"] for row in rows}
    assert all(row["relrowsecurity"] for row in rows)
    policies = admin.execute(
        "SELECT tablename, roles, qual, with_check FROM pg_policies "
        "WHERE schemaname = 'public'"
    ).fetchall()
    assert {row["tablename"] for row in policies} == APP_TABLES
    assert all(
        row["roles"] == ["career_pair_runtime"]
        and row["qual"] == "true" and row["with_check"] == "true"
        for row in policies
    )


def test_submission_migration_preserves_legacy_content_without_guessing(admin):
    migration = Path(__file__).resolve().parents[1] / "migrations/002_message_submission.sql"
    with admin.transaction():
        admin.execute("CREATE TEMP TABLE messages (content text) ON COMMIT DROP")
        admin.execute("INSERT INTO messages (content) VALUES ('기존 문구')")
        admin.execute(migration.read_text())
        assert admin.execute("SELECT * FROM messages").fetchone() == {
            "content": "기존 문구", "selected_option_id": None, "submitted_content": None,
        }


def test_owner_references_supabase_auth_users(admin):
    definition = admin.execute(
        """
        SELECT pg_get_constraintdef(oid) AS definition
        FROM pg_constraint WHERE conname = 'records_owner_id_fkey'
        """
    ).fetchone()["definition"]
    assert "REFERENCES auth.users(id)" in definition


def test_message_question_must_belong_to_same_record(admin):
    _, record_a = _new_record(admin)
    _, record_b = _new_record(admin)
    question_b = uuid4()
    admin.execute(
        """
        INSERT INTO questions (id, record_id, sequence, content, options, input_revision)
        VALUES (%s, %s, 1, '다른 기록 질문', %s, 0)
        """,
        (question_b, record_b, Jsonb([])),
    )

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin.execute(
            """
            INSERT INTO messages
                (record_id, question_id, sequence, sender, content, input_revision)
            VALUES (%s, %s, 1, 'assistant', 'AI 응답', 0)
            """,
            (record_a, question_b),
        )


def test_user_message_requires_client_message_id(admin):
    _, record_id = _new_record(admin)
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO messages
                (record_id, question_id, sequence, sender, content, input_revision)
            VALUES (%s, NULL, 1, 'user', '답변', 0)
            """,
            (record_id,),
        )


def test_client_message_id_is_unique_per_record(admin):
    _, record_id = _new_record(admin)
    client_id = uuid4()
    for sequence in (1, 2):
        if sequence == 1:
            admin.execute(
                """
                INSERT INTO messages
                    (record_id, sequence, sender, content, client_message_id, input_revision)
                VALUES (%s, %s, 'user', '답변', %s, 0)
                """,
                (record_id, sequence, client_id),
            )
        else:
            with pytest.raises(psycopg.errors.UniqueViolation):
                admin.execute(
                    """
                    INSERT INTO messages
                        (record_id, sequence, sender, content, client_message_id, input_revision)
                    VALUES (%s, %s, 'user', '다른 답변', %s, 0)
                    """,
                    (record_id, sequence, client_id),
                )


def test_sequence_is_unique_per_record(admin):
    _, record_id = _new_record(admin)
    admin.execute(
        """
        INSERT INTO messages
            (record_id, sequence, sender, content, input_revision)
        VALUES (%s, 1, 'assistant', 'AI', 0)
        """,
        (record_id,),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            """
            INSERT INTO messages
                (record_id, sequence, sender, content, input_revision)
            VALUES (%s, 1, 'assistant', 'AI 2', 0)
            """,
            (record_id,),
        )


def test_provider_links_have_composite_primary_keys(admin):
    provider_id, region_id, work_type_id = uuid4(), uuid4(), uuid4()
    admin.execute(
        "INSERT INTO providers (id, name, phone) VALUES (%s, '업체', '000')",
        (provider_id,),
    )
    admin.execute(
        "INSERT INTO regions (id, name, display_name) VALUES (%s, '동', '시 동')",
        (region_id,),
    )
    admin.execute(
        "INSERT INTO work_types (id, name) VALUES (%s, '곰팡이')",
        (work_type_id,),
    )
    admin.execute(
        "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
        (provider_id, region_id),
    )
    admin.execute(
        "INSERT INTO provider_work_types (provider_id, work_type_id) VALUES (%s, %s)",
        (provider_id, work_type_id),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
            (provider_id, region_id),
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            "INSERT INTO provider_work_types (provider_id, work_type_id) VALUES (%s, %s)",
            (provider_id, work_type_id),
        )


def test_reverse_provider_indexes_exist(admin):
    names = {
        row["indexname"]
        for row in admin.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        ).fetchall()
    }
    assert "provider_regions_region_id_idx" in names
    assert "provider_work_types_work_type_id_idx" in names
    assert "records_owner_id_idx" in names


def test_photo_files_and_coordinates_are_not_stored(admin):
    columns = {
        row["column_name"]
        for row in admin.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'records'
            """
        ).fetchall()
    }
    assert "photo_observations" in columns
    forbidden = {"photo_url", "photo_path", "photo_file", "image_url", "image_path"}
    assert columns.isdisjoint(forbidden)
    all_tables = {
        row["table_name"]
        for row in admin.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    }
    assert "photo_files" not in all_tables
    assert "storage" not in all_tables


def test_runtime_role_cannot_read_auth_schema_or_create_tables():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM auth.users")
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE runtime_should_not_ddl (id int)")
        conn.rollback()


def test_runtime_role_has_only_required_privileges():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute("SELECT count(*) FROM records").fetchone() is not None
        assert conn.execute("SELECT count(*) FROM questions").fetchone() is not None
        assert conn.execute("SELECT count(*) FROM messages").fetchone() is not None
        assert conn.execute("SELECT count(*) FROM providers").fetchone() is not None

        for table, privilege in (
            ("questions", "INSERT"),
            ("questions", "UPDATE"),
        ):
            assert conn.execute(
                "SELECT has_table_privilege(current_user, %s, %s)",
                (table, privilege),
            ).fetchone()[0]

        for statement in (
            "DELETE FROM records",
            "INSERT INTO providers (name, phone) VALUES ('업체', '000')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
            conn.rollback()
