-- Local development stand-in for Supabase Auth. On Supabase these already exist,
-- Skip DDL entirely when present: Supabase does not grant CREATE on auth.
DO $$
BEGIN
    IF to_regclass('auth.users') IS NULL THEN
        CREATE SCHEMA IF NOT EXISTS auth;
        CREATE TABLE auth.users (id uuid PRIMARY KEY);
    END IF;
END
$$;

CREATE TABLE records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    location text,
    symptoms text,
    photo_observations jsonb,
    input_revision bigint NOT NULL DEFAULT 0 CHECK (input_revision >= 0),
    next_question_result jsonb,
    next_question_revision bigint,
    diagnosis jsonb,
    diagnosis_revision bigint,
    diagnosis_generation bigint NOT NULL DEFAULT 0 CHECK (diagnosis_generation >= 0),
    landlord_draft text,
    landlord_draft_revision bigint,
    landlord_draft_diagnosis_generation bigint,
    provider_draft text,
    provider_draft_revision bigint,
    provider_draft_diagnosis_generation bigint,
    conversation_sequence bigint NOT NULL DEFAULT 0 CHECK (conversation_sequence >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX records_owner_id_idx ON records (owner_id);

CREATE TABLE questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id uuid NOT NULL REFERENCES records (id) ON DELETE CASCADE,
    sequence bigint NOT NULL CHECK (sequence > 0),
    content text NOT NULL,
    options jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(options) = 'array'),
    answered boolean NOT NULL DEFAULT false,
    input_revision bigint NOT NULL CHECK (input_revision >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT questions_record_sequence_key UNIQUE (record_id, sequence),
    -- Target of the composite FK below, which keeps a message's question in the same record.
    CONSTRAINT questions_record_id_id_key UNIQUE (record_id, id)
);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id uuid NOT NULL REFERENCES records (id) ON DELETE CASCADE,
    question_id uuid,
    sequence bigint NOT NULL CHECK (sequence > 0),
    sender text NOT NULL CHECK (sender IN ('user', 'assistant')),
    content text NOT NULL,
    client_message_id uuid,
    input_revision bigint NOT NULL CHECK (input_revision >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT messages_user_client_message_id_check
        CHECK (sender <> 'user' OR client_message_id IS NOT NULL),
    CONSTRAINT messages_record_sequence_key UNIQUE (record_id, sequence),
    CONSTRAINT messages_record_client_message_id_key UNIQUE (record_id, client_message_id),
    CONSTRAINT messages_question_same_record_fkey FOREIGN KEY (record_id, question_id)
        REFERENCES questions (record_id, id) ON DELETE CASCADE
);

CREATE INDEX messages_record_question_idx ON messages (record_id, question_id)
    WHERE question_id IS NOT NULL;

CREATE TABLE providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    phone text NOT NULL
);

CREATE TABLE regions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    display_name text NOT NULL
);

CREATE TABLE work_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE provider_regions (
    provider_id uuid NOT NULL REFERENCES providers (id) ON DELETE CASCADE,
    region_id uuid NOT NULL REFERENCES regions (id) ON DELETE CASCADE,
    PRIMARY KEY (provider_id, region_id)
);

CREATE INDEX provider_regions_region_id_idx ON provider_regions (region_id, provider_id);

CREATE TABLE provider_work_types (
    provider_id uuid NOT NULL REFERENCES providers (id) ON DELETE CASCADE,
    work_type_id uuid NOT NULL REFERENCES work_types (id) ON DELETE CASCADE,
    PRIMARY KEY (provider_id, work_type_id)
);

CREATE INDEX provider_work_types_work_type_id_idx
    ON provider_work_types (work_type_id, provider_id);

-- Runtime role: no DDL, no auth schema access, DML on app tables only.
-- Migration/admin runs as a separate account (MIGRATION_DATABASE_URL).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'career_pair_runtime') THEN
        EXECUTE 'CREATE ROLE career_pair_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO career_pair_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE records TO career_pair_runtime;
GRANT SELECT, DELETE ON TABLE questions TO career_pair_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE messages TO career_pair_runtime;
GRANT SELECT ON TABLE
    providers, regions, work_types, provider_regions, provider_work_types
    TO career_pair_runtime;

-- Keep app tables out of Supabase's Data API roles. No-ops on a plain PostgreSQL.
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE records, questions, messages, providers, '
                'regions, work_types, provider_regions, provider_work_types FROM %I',
                role_name
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$;
