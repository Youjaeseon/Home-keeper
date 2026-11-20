-- Region ancestry supports province-level programs for district/city users.
ALTER TABLE regions ADD COLUMN IF NOT EXISTS parent_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'regions_parent_id_fkey'
    ) THEN
        ALTER TABLE regions
            ADD CONSTRAINT regions_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES regions (id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS regions_parent_id_idx ON regions (parent_id);

-- Existing demo region: Yongin belongs to Gyeonggi Province.
INSERT INTO regions (name, display_name)
VALUES ('gyeonggi', '경기도')
ON CONFLICT (name) DO NOTHING;

UPDATE regions
SET parent_id = (SELECT id FROM regions WHERE name = 'gyeonggi')
WHERE name = 'yongin' AND parent_id IS NULL;

CREATE TABLE support_programs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text NOT NULL UNIQUE,
    source text NOT NULL CHECK (source IN ('seed', 'gov24_api')),
    title text NOT NULL,
    summary text NOT NULL,
    organization_name text NOT NULL,
    region_scope text NOT NULL CHECK (region_scope IN ('national', 'local')),
    region_id uuid REFERENCES regions (id),
    target_housing_types text[] NOT NULL DEFAULT '{}'::text[]
        CHECK (
            target_housing_types
            <@ ARRAY['monthly_rent', 'jeonse', 'semi_jeonse', 'owned', 'other']::text[]
        ),
    support_target text NOT NULL,
    support_content text NOT NULL,
    selection_criteria text,
    apply_method text,
    deadline_text text,
    deadline_date date,
    deadline_kind text NOT NULL
        CHECK (deadline_kind IN ('fixed', 'always_open', 'unknown')),
    detail_url text NOT NULL
        CHECK (detail_url ~* '^https?://[^[:space:]]+$'),
    source_attribution text NOT NULL,
    source_checked_at timestamptz NOT NULL DEFAULT now(),
    synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (region_scope = 'national' AND region_id IS NULL)
        OR (region_scope = 'local' AND region_id IS NOT NULL)
    ),
    CHECK (
        (deadline_kind = 'fixed' AND deadline_date IS NOT NULL)
        OR (deadline_kind IN ('always_open', 'unknown') AND deadline_date IS NULL)
    )
);

CREATE INDEX support_programs_region_deadline_idx
    ON support_programs (region_scope, region_id, deadline_date);

CREATE INDEX support_programs_source_synced_idx
    ON support_programs (source, synced_at DESC);

ALTER TABLE support_programs ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON support_programs TO career_pair_runtime
    USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON TABLE support_programs TO career_pair_runtime;

-- Keep the new app table out of Supabase Data API roles.
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE support_programs FROM %I', role_name);
        END IF;
    END LOOP;
END
$$;
