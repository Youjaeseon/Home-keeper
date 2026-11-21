-- Quote requests (1:N open requests) and provider proposals (one per provider).
-- Photos are private Storage paths; clients receive only signed URLs.

ALTER TABLE public.records
    ADD COLUMN IF NOT EXISTS photo_files jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(photo_files) = 'array');

CREATE TABLE quote_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id uuid NOT NULL REFERENCES records (id) ON DELETE CASCADE,
    requester_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    region_id uuid NOT NULL REFERENCES regions (id),
    work_type_id uuid NOT NULL REFERENCES work_types (id),
    address text,
    location text NOT NULL CHECK (length(btrim(location)) > 0),
    material text,
    memo text,
    photo_files jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(photo_files) = 'array'),
    severity_score integer
        CHECK (severity_score IS NULL OR (severity_score >= 0 AND severity_score <= 100)),
    severity_level text
        CHECK (severity_level IS NULL OR severity_level IN ('low', 'medium', 'high', 'undetermined')),
    suspected_types text[] NOT NULL DEFAULT '{}'::text[],
    status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'cancelled')),
    accepted_proposal_id uuid,
    accepted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX quote_requests_record_open_key
    ON quote_requests (record_id) WHERE status = 'open';
CREATE INDEX quote_requests_match_idx
    ON quote_requests (region_id, work_type_id, status, created_at DESC);
CREATE INDEX quote_requests_requester_idx
    ON quote_requests (requester_id, created_at DESC);

CREATE TABLE quote_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid NOT NULL REFERENCES quote_requests (id) ON DELETE CASCADE,
    provider_id uuid NOT NULL REFERENCES providers (id) ON DELETE CASCADE,
    min_price integer NOT NULL CHECK (min_price >= 0),
    max_price integer NOT NULL CHECK (max_price >= min_price),
    memo text NOT NULL
        CHECK (length(btrim(memo)) > 0 AND char_length(memo) <= 2000),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT quote_proposals_request_provider_key UNIQUE (request_id, provider_id)
);

CREATE UNIQUE INDEX quote_proposals_request_accepted_key
    ON quote_proposals (request_id) WHERE status = 'accepted';

ALTER TABLE quote_requests
    ADD CONSTRAINT quote_requests_accepted_proposal_fkey
    FOREIGN KEY (accepted_proposal_id) REFERENCES quote_proposals (id);

ALTER TABLE quote_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON quote_requests TO career_pair_runtime
    USING (true) WITH CHECK (true);

ALTER TABLE quote_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY backend_access ON quote_proposals TO career_pair_runtime
    USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON TABLE quote_requests, quote_proposals
    TO career_pair_runtime;

-- Keep the new app tables out of Supabase Data API roles.
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE quote_requests, quote_proposals FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$;
