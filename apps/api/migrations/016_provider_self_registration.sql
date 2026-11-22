-- Provider self-registration (POST /me/provider): users who sign up as 업체 create their own
-- providers row, linked to their auth user, with one 활동 지역 and optional work types.
-- Decision (Hyeok, 2026-11-22): reverses the earlier "업체는 사전 등록" rule (GAP-003).
-- RLS policy backend_access (003) already allows the runtime role on these tables; only grants are missing.
GRANT INSERT, UPDATE ON TABLE providers TO career_pair_runtime;
GRANT INSERT, DELETE ON TABLE provider_regions, provider_work_types TO career_pair_runtime;
