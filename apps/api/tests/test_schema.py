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
    "profiles",
    "support_programs",
    "chat_rooms",
    "chat_messages",
    "quote_requests",
    "quote_proposals",
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
    assert "007_profiles_and_regions.sql" in versions
    assert "008_support_programs.sql" in versions
    assert "009_support_program_seed.sql" in versions
    assert "010_chat_and_provider_accounts.sql" in versions
    assert "011_chat_read_state.sql" in versions
    assert "012_records_region.sql" in versions
    assert "013_provider_details.sql" in versions
    assert "014_yongin_provider_seed.sql" in versions
    assert "015_quote_requests_and_proposals.sql" in versions


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


def test_records_region_column_and_index(admin):
    column = admin.execute(
        """
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'records'
          AND column_name = 'region_id'
        """
    ).fetchone()
    assert column == {"data_type": "uuid", "is_nullable": "YES"}
    index = admin.execute(
        """
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = 'records_region_id_idx'
        """
    ).fetchone()
    assert index is not None
    assert "WHERE (region_id IS NOT NULL)" in index["indexdef"]


def test_records_photo_files_column(admin):
    column = admin.execute(
        """
        SELECT data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'records'
          AND column_name = 'photo_files'
        """
    ).fetchone()
    assert column["data_type"] == "jsonb"
    assert column["is_nullable"] == "NO"
    assert column["column_default"] == "'[]'::jsonb"


def test_quote_request_constraints_and_indexes(admin):
    names = {
        row["indexname"]
        for row in admin.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        ).fetchall()
    }
    for name in (
        "quote_requests_record_open_key",
        "quote_requests_match_idx",
        "quote_requests_requester_idx",
        "quote_proposals_request_provider_key",
        "quote_proposals_request_accepted_key",
    ):
        assert name in names
    fk = admin.execute(
        """
        SELECT 1 FROM pg_constraint
        WHERE conname = 'quote_requests_accepted_proposal_fkey'
        """
    ).fetchone()
    assert fk is not None


def test_provider_detail_columns_and_rating_index(admin):
    columns = {
        row["column_name"]: (row["data_type"], row["is_nullable"])
        for row in admin.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'providers'
            """
        ).fetchall()
    }
    assert columns["rating"] == ("numeric", "NO")
    assert columns["review_count"] == ("integer", "NO")
    assert columns["description"] == ("text", "YES")
    assert columns["address"] == ("text", "YES")
    assert columns["business_hours"] == ("text", "YES")
    assert columns["career_years"] == ("integer", "YES")
    index = admin.execute(
        """
        SELECT indexdef FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = 'providers_rating_idx'
        """
    ).fetchone()
    assert index is not None
    assert "rating DESC" in index["indexdef"]


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
    assert "records_owner_id_updated_at_idx" in names
    assert "records_region_id_idx" in names
    assert "providers_rating_idx" in names
    assert "profiles_region_id_idx" in names
    assert "regions_parent_id_idx" in names
    assert "support_programs_region_deadline_idx" in names
    assert "support_programs_source_synced_idx" in names
    assert "providers_account_user_id_key" in names
    assert "chat_rooms_requester_provider_key" in names
    assert "chat_rooms_requester_last_message_idx" in names
    assert "chat_rooms_provider_last_message_idx" in names
    assert "chat_messages_room_created_idx" in names
    assert "chat_messages_room_client_message_id_key" in names


def test_support_program_schema_and_seeded_programs(admin):
    columns = {
        row["column_name"]
        for row in admin.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'support_programs'
            """
        ).fetchall()
    }
    assert {
        "id",
        "external_id",
        "source",
        "title",
        "summary",
        "organization_name",
        "region_scope",
        "region_id",
        "target_housing_types",
        "categories",
        "support_target",
        "support_content",
        "selection_criteria",
        "apply_method",
        "deadline_text",
        "deadline_date",
        "deadline_kind",
        "detail_url",
        "source_attribution",
        "source_checked_at",
        "synced_at",
        "created_at",
        "updated_at",
    } <= columns

    regions = {
        row["name"]: row
        for row in admin.execute(
            "SELECT id, name, display_name, parent_id FROM regions"
        ).fetchall()
    }
    assert regions["gyeonggi"]["display_name"] == "경기도"
    assert regions["yongin"]["parent_id"] == regions["gyeonggi"]["id"]

    seeded = admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE source = 'seed'"
    ).fetchone()["count"]
    assert seeded == 4
    seed_categories = {
        row["external_id"]: row["categories"]
        for row in admin.execute(
            "SELECT external_id, categories FROM support_programs WHERE source = 'seed'"
        ).fetchall()
    }
    assert seed_categories["seed:gov24-youth-monthly-rent-2026"] == [
        "monthly_rent_support"
    ]
    assert seed_categories["seed:gyeonggi-independent-youth-housing-2026"] == [
        "deposit_loan"
    ]
    assert seed_categories["seed:yongin-youth-brokerage-fee-2026"] == [
        "brokerage_fee"
    ]
    assert seed_categories["seed:yongin-youth-monthly-rent-2026"] == [
        "monthly_rent_support"
    ]
    assert admin.execute(
        "SELECT count(*) AS count FROM support_programs WHERE detail_url !~* '^https?://'"
    ).fetchone()["count"] == 0


def test_support_program_rejects_invalid_url_and_deadline(admin):
    def values(**overrides):
        program = {
            "external_id": f"test-invalid-{uuid4()}",
            "source": "seed",
            "title": "검증용",
            "summary": "검증용",
            "organization_name": "검증기관",
            "region_scope": "national",
            "region_id": None,
            "target_housing_types": [],
            "support_target": "검증 대상",
            "support_content": "검증 내용",
            "selection_criteria": None,
            "apply_method": None,
            "deadline_text": None,
            "deadline_date": None,
            "deadline_kind": "unknown",
            "detail_url": "https://example.com/program",
            "source_attribution": "검증",
        }
        program.update(overrides)
        return program

    invalid_url = values(detail_url="ftp://example.com/program")
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO support_programs
                (external_id, source, title, summary, organization_name,
                 region_scope, region_id, target_housing_types, support_target,
                 support_content, selection_criteria, apply_method, deadline_text,
                 deadline_date, deadline_kind, detail_url, source_attribution)
            VALUES
                (%(external_id)s, %(source)s, %(title)s, %(summary)s,
                 %(organization_name)s, %(region_scope)s, %(region_id)s,
                 %(target_housing_types)s, %(support_target)s, %(support_content)s,
                 %(selection_criteria)s, %(apply_method)s, %(deadline_text)s,
                 %(deadline_date)s, %(deadline_kind)s, %(detail_url)s,
                 %(source_attribution)s)
            """,
            invalid_url,
        )

    invalid_deadline = values(
        deadline_kind="fixed",
        deadline_text="2026. 13. 01.",
        deadline_date=None,
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO support_programs
                (external_id, source, title, summary, organization_name,
                 region_scope, region_id, target_housing_types, support_target,
                 support_content, selection_criteria, apply_method, deadline_text,
                 deadline_date, deadline_kind, detail_url, source_attribution)
            VALUES
                (%(external_id)s, %(source)s, %(title)s, %(summary)s,
                 %(organization_name)s, %(region_scope)s, %(region_id)s,
                 %(target_housing_types)s, %(support_target)s, %(support_content)s,
                 %(selection_criteria)s, %(apply_method)s, %(deadline_text)s,
                 %(deadline_date)s, %(deadline_kind)s, %(detail_url)s,
                 %(source_attribution)s)
            """,
            invalid_deadline,
        )


def test_profiles_table_and_seeded_demo_region(admin):
    columns = {
        row["column_name"]
        for row in admin.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'profiles'
            """
        ).fetchall()
    }
    assert {
        "user_id",
        "nickname",
        "role",
        "region_id",
        "address",
        "housing_type",
        "created_at",
        "updated_at",
    } <= columns

    region = admin.execute(
        "SELECT id, display_name FROM regions WHERE name = 'yongin'"
    ).fetchone()
    assert region is not None
    assert region["display_name"] == "경기도 용인시"


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
        assert conn.execute("SELECT count(*) FROM profiles").fetchone() is not None
        assert conn.execute("SELECT count(*) FROM support_programs").fetchone() is not None

        for table, privilege in (
            ("chat_rooms", "SELECT"),
            ("chat_rooms", "INSERT"),
            ("chat_rooms", "UPDATE"),
            ("chat_messages", "SELECT"),
            ("chat_messages", "INSERT"),
            ("questions", "INSERT"),
            ("questions", "UPDATE"),
            ("profiles", "INSERT"),
            ("profiles", "UPDATE"),
            ("support_programs", "INSERT"),
            ("support_programs", "UPDATE"),
        ):
            assert conn.execute(
                "SELECT has_table_privilege(current_user, %s, %s)",
                (table, privilege),
            ).fetchone()[0]

        for statement in (
            "DELETE FROM records",
            "DELETE FROM profiles",
            "DELETE FROM support_programs",
            "INSERT INTO providers (name, phone) VALUES ('업체', '000')",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
            conn.rollback()


def test_provider_account_link_and_chat_schema(admin):
    columns = {
        row["column_name"]: row
        for row in admin.execute(
            """
            SELECT column_name, is_nullable FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'providers'
            """
        ).fetchall()
    }
    assert columns["account_user_id"]["is_nullable"] == "YES"

    definition = admin.execute(
        """
        SELECT pg_get_constraintdef(oid) AS definition
        FROM pg_constraint WHERE conname = 'providers_account_user_id_fkey'
        """
    ).fetchone()["definition"]
    assert "REFERENCES auth.users(id)" in definition
    assert "ON DELETE SET NULL" in definition

    # Two providers cannot claim the same login; unlinked providers stay allowed.
    user_id = uuid4()
    admin.execute("INSERT INTO auth.users (id) VALUES (%s)", (user_id,))
    first, second = uuid4(), uuid4()
    admin.execute(
        "INSERT INTO providers (id, name, phone, account_user_id) VALUES (%s, 'A', '0', %s)",
        (first, user_id),
    )
    admin.execute(
        "INSERT INTO providers (id, name, phone) VALUES (%s, 'B', '0')",
        (second,),
    )
    admin.execute(
        "INSERT INTO providers (id, name, phone) VALUES (%s, 'C', '0')",
        (uuid4(),),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            "INSERT INTO providers (name, phone, account_user_id) VALUES ('D', '0', %s)",
            (user_id,),
        )


def test_chat_tables_constraints_and_work_type_seed(admin):
    work_types = {
        row["name"] for row in admin.execute("SELECT name FROM work_types").fetchall()
    }
    assert {"곰팡이 제거", "균열 보수", "벽지·도장 보수", "원인 점검"} <= work_types

    requester_id = uuid4()
    provider_user_id = uuid4()
    for user_id in (requester_id, provider_user_id):
        admin.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    provider_id = uuid4()
    admin.execute(
        "INSERT INTO providers (id, name, phone, account_user_id) VALUES (%s, '업체', '0', %s)",
        (provider_id, provider_user_id),
    )
    room_id = uuid4()
    admin.execute(
        "INSERT INTO chat_rooms (id, requester_id, provider_id) VALUES (%s, %s, %s)",
        (room_id, requester_id, provider_id),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            "INSERT INTO chat_rooms (requester_id, provider_id) VALUES (%s, %s)",
            (requester_id, provider_id),
        )

    client_id = uuid4()
    admin.execute(
        """
        INSERT INTO chat_messages
            (room_id, sender_id, sender_role, message_type, content, client_message_id)
        VALUES (%s, %s, 'requester', 'text', '안녕하세요', %s)
        """,
        (room_id, requester_id, client_id),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute(
            """
            INSERT INTO chat_messages
                (room_id, sender_id, sender_role, message_type, content, client_message_id)
            VALUES (%s, %s, 'requester', 'text', '다른 내용', %s)
            """,
            (room_id, requester_id, client_id),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO chat_messages
                (room_id, sender_id, sender_role, message_type, content, client_message_id)
            VALUES (%s, %s, 'admin', 'text', 'x', %s)
            """,
            (room_id, requester_id, uuid4()),
        )
    admin.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO chat_messages
                (room_id, sender_id, sender_role, message_type, content, client_message_id)
            VALUES (%s, %s, 'requester', 'text', '   ', %s)
            """,
            (room_id, requester_id, uuid4()),
        )
    admin.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(
            """
            INSERT INTO chat_messages
                (room_id, sender_id, sender_role, message_type, content, client_message_id)
            VALUES (%s, %s, 'requester', 'text', %s, %s)
            """,
            (room_id, requester_id, "x" * 2001, uuid4()),
        )
