-- Verified housing support programs, checked against the official pages on 2026-11-20.
-- Re-running this file is safe: stable seed IDs and ON CONFLICT DO NOTHING.
-- Sources:
--   https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004661
--   https://youth.gg.go.kr/gg/intro/youth-policy-educational-testing.do?articleNo=9010&mode=view
--   https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026021000000000000055001
--   https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026032300000000000061001

INSERT INTO support_programs (
    external_id,
    source,
    title,
    summary,
    organization_name,
    region_scope,
    region_id,
    target_housing_types,
    support_target,
    support_content,
    selection_criteria,
    apply_method,
    deadline_text,
    deadline_date,
    deadline_kind,
    detail_url,
    source_attribution
)
VALUES (
    'seed:gov24-youth-monthly-rent-2026',
    'seed',
    '청년월세 지원사업',
    '고금리·고물가 등으로 경제적 어려움을 겪는 청년층의 주거비 부담 경감을 위해 월 최대 20만원씩 최장 24개월간 월세를 지원합니다(생애 1회).',
    '국토교통부',
    'national',
    NULL,
    ARRAY['monthly_rent']::text[],
    '19세~34세 독립거주 무주택 청년 중 청년가구 소득이 기준 중위소득 60% 이하이면서, 원가구 소득이 기준 중위소득 100% 이하인 청년',
    '월세로 거주하는 청년을 대상으로 실제 납부하는 임대료를 최대 480만원(월 최대 20만원)까지 최대 24개월(회) 동안 매월 분할하여 지원합니다.',
    NULL,
    '주소지 관할 주민센터에 청년 본인이 방문하거나 복지로(bokjiro.go.kr)에서 온라인으로 신청',
    '2026년 신규수혜자 신청접수 기간: 3.30(월) 09:00 ~ 5.29(금) 16:00까지',
    DATE '2026-05-29',
    'fixed',
    'https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004661',
    '복지로 · 국토교통부'
),
(
    'seed:gyeonggi-independent-youth-housing-2026',
    'seed',
    '자립준비청년 주거비 지원사업',
    '자립준비청년의 주거불안 해소와 주거자립 지원',
    '경기도 · 경기주택도시공사',
    'local',
    (SELECT id FROM regions WHERE name = 'gyeonggi'),
    ARRAY[]::text[],
    '아동·청소년복지시설, 가정위탁 퇴소 5년 이내 자립준비청년 · 연령 무관 · 소득기준: 행복주택(월평균소득 100%), 통합공공임대(중위소득 100%), 매입임대·전세임대(소득 무관)',
    '자립준비청년이 경기주택도시공사 공공임대주택에 입주하는 경우, 표준 임대보증금 전액 지원',
    NULL,
    NULL,
    NULL,
    NULL,
    'unknown',
    'https://youth.gg.go.kr/gg/intro/youth-policy-educational-testing.do?articleNo=9010&mode=view',
    '경기청년포털 · 경기도'
),
(
    'seed:yongin-youth-brokerage-fee-2026',
    'seed',
    '용인청년 부동산 중개보수 감면',
    '민관 협력을 통해 상대적으로 경제적 기반이 부족한 청년 임차인에게 부동산 중개보수를 경감해 줌으로써 지역 상생형 주거문화를 조성',
    '용인시',
    'local',
    (SELECT id FROM regions WHERE name = 'yongin'),
    ARRAY['monthly_rent', 'jeonse']::text[],
    '18~34세 청년',
    '용인시 청년우대 착한부동산에서 전·월세보증금 1억원 미만 계약 시 부동산 중개보수 20% 이상 감면',
    NULL,
    '착한부동산 목록, 위치 확인 후 중개사무소 방문하여 감면',
    '2026-01-01 00:00 ~ 2026-12-31 00:00',
    DATE '2026-12-31',
    'fixed',
    'https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026021000000000000055001',
    '용인청년포털 · 용인시'
),
(
    'seed:yongin-youth-monthly-rent-2026',
    'seed',
    '청년월세 지원',
    '경제적 어려움을 겪고 있는 청년층의 주거비 부담 완화를 위해 청년 월세를 지원',
    '용인시',
    'local',
    (SELECT id FROM regions WHERE name = 'yongin'),
    ARRAY['monthly_rent']::text[],
    '19~34세 부모님과 별도 거주 무주택 청년으로 원가구 기준중위소득 100% 이하, 재산 4억 7천만원 이하, 청년본인 기준중위소득 60% 이하, 재산 1억 2천2백만원 이하',
    '월 20만원씩 최대 24개월 월세 지원',
    NULL,
    '온라인: 복지로(bokjiro.go.kr), 방문: 용인시청 또는 주소지 관할 행정복지센터',
    '2026-03-30 09:00 ~ 2026-05-29 16:00',
    DATE '2026-05-29',
    'fixed',
    'https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026032300000000000061001',
    '용인청년포털 · 용인시'
)
ON CONFLICT (external_id) DO NOTHING;
