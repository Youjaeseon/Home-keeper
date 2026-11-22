-- Capital-area (수도권) region seed so profiles, provider matching, quote
-- requests, and Gov24 support-program sync have real regions to resolve.
--
-- Scope: 3 시·도 + 서울 25 자치구 + 경기 31 시·군 + 인천 9 구 2 군.
-- Checked 2026-11-22 against:
--   https://www.incheon.go.kr (인천 9구 2군: 제물포·영종·미추홀·연수·남동·부평·계양·서해·검단 + 강화·옹진, 2026-07-01 개편)
--   https://ko.wikipedia.org/wiki/경기도, 서울특별시, 인천광역시 (행정 구역 표)
-- `name` is an opaque slug for SQL/tests only; clients display `display_name`.
-- Re-running is safe: `ON CONFLICT (name) DO NOTHING` keeps existing rows
-- (including the demo `yongin` from 007 and its parent from 008).
--
-- shortcut: Gov24 rows that still name pre-2026 인천 기관(중구·동구·서구) are
-- dropped by app/support_sync.py region resolution; upgrade when that data moves.
-- 근거: support_sync.py `_resolve_region`은 display_name의 전체/마지막 토큰과
-- `...청`만 정확 일치로 인정한다. 그래서 display_name은 "경기도 용인시" 꼴로 둔다.

WITH seed(name, display_name) AS (
    VALUES
        ('gyeonggi', '경기도'),
        ('seoul', '서울특별시'),
        ('incheon', '인천광역시')
)
INSERT INTO regions (name, display_name)
SELECT name, display_name FROM seed
ON CONFLICT (name) DO NOTHING;

WITH seed(name, display_name, parent_name) AS (
    VALUES
        -- 서울특별시 25 자치구
        ('seoul_jongno', '서울특별시 종로구', 'seoul'),
        ('seoul_jung', '서울특별시 중구', 'seoul'),
        ('seoul_yongsan', '서울특별시 용산구', 'seoul'),
        ('seoul_seongdong', '서울특별시 성동구', 'seoul'),
        ('seoul_gwangjin', '서울특별시 광진구', 'seoul'),
        ('seoul_dongdaemun', '서울특별시 동대문구', 'seoul'),
        ('seoul_jungnang', '서울특별시 중랑구', 'seoul'),
        ('seoul_seongbuk', '서울특별시 성북구', 'seoul'),
        ('seoul_gangbuk', '서울특별시 강북구', 'seoul'),
        ('seoul_dobong', '서울특별시 도봉구', 'seoul'),
        ('seoul_nowon', '서울특별시 노원구', 'seoul'),
        ('seoul_eunpyeong', '서울특별시 은평구', 'seoul'),
        ('seoul_seodaemun', '서울특별시 서대문구', 'seoul'),
        ('seoul_mapo', '서울특별시 마포구', 'seoul'),
        ('seoul_yangcheon', '서울특별시 양천구', 'seoul'),
        ('seoul_gangseo', '서울특별시 강서구', 'seoul'),
        ('seoul_guro', '서울특별시 구로구', 'seoul'),
        ('seoul_geumcheon', '서울특별시 금천구', 'seoul'),
        ('seoul_yeongdeungpo', '서울특별시 영등포구', 'seoul'),
        ('seoul_dongjak', '서울특별시 동작구', 'seoul'),
        ('seoul_gwanak', '서울특별시 관악구', 'seoul'),
        ('seoul_seocho', '서울특별시 서초구', 'seoul'),
        ('seoul_gangnam', '서울특별시 강남구', 'seoul'),
        ('seoul_songpa', '서울특별시 송파구', 'seoul'),
        ('seoul_gangdong', '서울특별시 강동구', 'seoul'),
        -- 경기도 31 시·군 (yongin은 007에서 이미 생성됨)
        ('suwon', '경기도 수원시', 'gyeonggi'),
        ('seongnam', '경기도 성남시', 'gyeonggi'),
        ('uijeongbu', '경기도 의정부시', 'gyeonggi'),
        ('anyang', '경기도 안양시', 'gyeonggi'),
        ('bucheon', '경기도 부천시', 'gyeonggi'),
        ('gwangmyeong', '경기도 광명시', 'gyeonggi'),
        ('pyeongtaek', '경기도 평택시', 'gyeonggi'),
        ('dongducheon', '경기도 동두천시', 'gyeonggi'),
        ('ansan', '경기도 안산시', 'gyeonggi'),
        ('goyang', '경기도 고양시', 'gyeonggi'),
        ('gwacheon', '경기도 과천시', 'gyeonggi'),
        ('guri', '경기도 구리시', 'gyeonggi'),
        ('namyangju', '경기도 남양주시', 'gyeonggi'),
        ('osan', '경기도 오산시', 'gyeonggi'),
        ('siheung', '경기도 시흥시', 'gyeonggi'),
        ('gunpo', '경기도 군포시', 'gyeonggi'),
        ('uiwang', '경기도 의왕시', 'gyeonggi'),
        ('hanam', '경기도 하남시', 'gyeonggi'),
        ('yongin', '경기도 용인시', 'gyeonggi'),
        ('paju', '경기도 파주시', 'gyeonggi'),
        ('icheon', '경기도 이천시', 'gyeonggi'),
        ('anseong', '경기도 안성시', 'gyeonggi'),
        ('gimpo', '경기도 김포시', 'gyeonggi'),
        ('hwaseong', '경기도 화성시', 'gyeonggi'),
        ('gwangju_gyeonggi', '경기도 광주시', 'gyeonggi'),
        ('yangju', '경기도 양주시', 'gyeonggi'),
        ('pocheon', '경기도 포천시', 'gyeonggi'),
        ('yeoju', '경기도 여주시', 'gyeonggi'),
        ('yeoncheon', '경기도 연천군', 'gyeonggi'),
        ('gapyeong', '경기도 가평군', 'gyeonggi'),
        ('yangpyeong', '경기도 양평군', 'gyeonggi'),
        -- 인천광역시 9 구 2 군
        ('incheon_jemulpo', '인천광역시 제물포구', 'incheon'),
        ('incheon_yeongjong', '인천광역시 영종구', 'incheon'),
        ('incheon_michuhol', '인천광역시 미추홀구', 'incheon'),
        ('incheon_yeonsu', '인천광역시 연수구', 'incheon'),
        ('incheon_namdong', '인천광역시 남동구', 'incheon'),
        ('incheon_bupyeong', '인천광역시 부평구', 'incheon'),
        ('incheon_gyeyang', '인천광역시 계양구', 'incheon'),
        ('incheon_seohae', '인천광역시 서해구', 'incheon'),
        ('incheon_geomdan', '인천광역시 검단구', 'incheon'),
        ('incheon_ganghwa', '인천광역시 강화군', 'incheon'),
        ('incheon_ongjin', '인천광역시 옹진군', 'incheon')
),
resolved AS (
    SELECT seed.name, seed.display_name, parent.id AS parent_id
    FROM seed
    LEFT JOIN regions AS parent ON parent.name = seed.parent_name
)
INSERT INTO regions (name, display_name, parent_id)
SELECT name, display_name, parent_id FROM resolved
ON CONFLICT (name) DO NOTHING;

-- Grant path for the sync/maintenance commands is table-level (008); new rows
-- need no extra privileges.
