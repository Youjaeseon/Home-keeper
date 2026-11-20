CREATE TABLE profiles (
    user_id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    nickname text NOT NULL CHECK (length(btrim(nickname)) > 0),
    role text NOT NULL DEFAULT 'requester'
        CHECK (role IN ('requester', 'provider')),
    region_id uuid NOT NULL REFERENCES regions (id),
    address text,
    housing_type text NOT NULL
        CHECK (housing_type IN ('monthly_rent', 'jeonse', 'semi_jeonse', 'owned', 'other')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX profiles_region_id_idx ON profiles (region_id);

-- Yongin is the agreed demo region; preserve any existing row with the same name.
INSERT INTO regions (name, display_name)
VALUES ('yongin', '경기도 용인시')
ON CONFLICT (name) DO NOTHING;

-- Supports the "내 정보" record list.
CREATE INDEX IF NOT EXISTS records_owner_id_updated_at_idx
    ON records (owner_id, updated_at DESC);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON profiles TO career_pair_runtime
    USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON TABLE profiles TO career_pair_runtime;

-- Keep the new app table out of Supabase Data API roles.
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE profiles FROM %I', role_name);
        END IF;
    END LOOP;
END
$$;
