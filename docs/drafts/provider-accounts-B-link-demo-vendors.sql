-- DRAFT (NOT APPLIED). Option (B): link pre-created vendor logins to existing provider rows.
-- 1) In Supabase Auth, create one login per demo vendor (email + password), e.g. vendor01@example.com.
-- 2) Run this with an admin connection (not the runtime role). Replace the emails/names.
--    Each linked vendor then sees every open 견적 요청서 in its 출장 지역 and can send 업체 제안서.

-- Link a login to an existing provider row (repeat per vendor).
UPDATE providers
SET account_user_id = (SELECT id FROM auth.users WHERE email = 'vendor01@example.com')
WHERE name = '[테스트] 하자케어 01';

-- Make the app treat that login as a provider (profile row is created on first app login;
-- run after the vendor has logged in once and registered a profile, or insert it here).
UPDATE profiles
SET role = 'provider'
WHERE user_id = (SELECT id FROM auth.users WHERE email = 'vendor01@example.com');

-- Check
SELECT p.name, u.email, pr.role
FROM providers p
JOIN auth.users u ON u.id = p.account_user_id
LEFT JOIN profiles pr ON pr.user_id = u.id;
