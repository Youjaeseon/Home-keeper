-- DRAFT (NOT APPLIED). Option (A): let users sign up as 업체 in the app.
-- Requires team agreement: this reverses GAP-003 ("업체는 사전 등록") and changes
-- grants on the shared Supabase DB. Run only with an admin connection, never the runtime role.
--
-- Backend work still needed if this is chosen (not implemented):
--   - PUT /me/profile (or a new POST /me/provider) accepts role=provider + 업체명·소개·지역·작업 종류,
--     inserts providers(account_user_id = auth user), provider_regions, provider_work_types,
--     and sets profiles.role = 'provider'.
--   - App: restore the 업체 option on signup with 업체명/소개/작업 종류 fields.

GRANT INSERT, UPDATE ON TABLE providers TO career_pair_runtime;
GRANT INSERT, DELETE ON TABLE provider_regions, provider_work_types TO career_pair_runtime;
