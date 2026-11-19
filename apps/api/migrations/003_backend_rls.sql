-- FastAPI checks ownership; only its private DB role may pass RLS.
DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'records', 'questions', 'messages', 'providers', 'regions',
        'work_types', 'provider_regions', 'provider_work_types'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'CREATE POLICY backend_access ON public.%I TO career_pair_runtime '
            'USING (true) WITH CHECK (true)', table_name
        );
    END LOOP;
END
$$;

ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.schema_migrations FROM PUBLIC;
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.schema_migrations FROM %I', role_name);
        END IF;
    END LOOP;
END
$$;
