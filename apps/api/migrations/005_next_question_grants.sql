-- next-question creates question rows and marks them answered as the runtime role.
-- Schema already has the needed columns; this only adds the least-privilege grant.
GRANT INSERT, UPDATE ON TABLE public.questions TO career_pair_runtime;
