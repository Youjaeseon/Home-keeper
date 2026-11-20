-- Requester-provider chat: provider account link, chat rooms, chat messages.
-- Provider account linking is admin-only (no runtime UPDATE grant on providers).

ALTER TABLE providers ADD COLUMN IF NOT EXISTS account_user_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'providers_account_user_id_fkey'
    ) THEN
        ALTER TABLE providers
            ADD CONSTRAINT providers_account_user_id_fkey
            FOREIGN KEY (account_user_id) REFERENCES auth.users (id) ON DELETE SET NULL;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS providers_account_user_id_key
    ON providers (account_user_id)
    WHERE account_user_id IS NOT NULL;

-- Work types used by provider search and diagnosis recommendations.
INSERT INTO work_types (name)
VALUES ('곰팡이 제거'), ('균열 보수'), ('벽지·도장 보수'), ('원인 점검')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE chat_rooms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    provider_id uuid NOT NULL REFERENCES providers (id) ON DELETE CASCADE,
    latest_record_id uuid REFERENCES records (id) ON DELETE SET NULL,
    last_message_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    -- One room per requester-provider pair; concurrent creates converge here.
    CONSTRAINT chat_rooms_requester_provider_key UNIQUE (requester_id, provider_id)
);

CREATE INDEX chat_rooms_requester_last_message_idx
    ON chat_rooms (requester_id, last_message_at DESC);

CREATE INDEX chat_rooms_provider_last_message_idx
    ON chat_rooms (provider_id, last_message_at DESC);

CREATE TABLE chat_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid NOT NULL REFERENCES chat_rooms (id) ON DELETE CASCADE,
    sender_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    sender_role text NOT NULL CHECK (sender_role IN ('requester', 'provider')),
    message_type text NOT NULL CHECK (message_type IN ('text', 'record_summary')),
    record_id uuid REFERENCES records (id) ON DELETE SET NULL,
    content text NOT NULL CHECK (length(btrim(content)) > 0 AND char_length(content) <= 2000),
    payload jsonb CHECK (payload IS NULL OR jsonb_typeof(payload) = 'object'),
    client_message_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_room_client_message_id_key
        UNIQUE (room_id, client_message_id)
);

CREATE INDEX chat_messages_room_created_idx
    ON chat_messages (room_id, created_at, id);

ALTER TABLE chat_rooms ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON chat_rooms TO career_pair_runtime
    USING (true) WITH CHECK (true);

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON chat_messages TO career_pair_runtime
    USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON TABLE chat_rooms, chat_messages TO career_pair_runtime;

-- Keep the new app tables out of Supabase Data API roles.
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE chat_rooms, chat_messages FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$;
