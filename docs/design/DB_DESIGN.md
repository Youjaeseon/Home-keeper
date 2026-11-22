# MVP DB 설계 초안

합의한 저장 규칙을 기준으로 정리한 테이블 설계다. 아래 테이블 표는 전체 설계 요약이며, 현재 실제 DB에 적용된 컬럼·타입은 마이그레이션(`001`–`011`)과 구현 확정 사항을 함께 확인한다. 접근·생성·실패 처리 규칙은 [백엔드 설계](BACKEND_DESIGN.md)를 따른다.

## 문서 범위

아래 구현 확정 사항은 현재 마이그레이션(`001`–`011`)에 반영된 내용이다.

2026년 11월 20일 팀 회의 변경 사항을 반영해 `records.material`, 샘플 일괄 분석 결과 저장, 회원 프로필(`profiles`), 지역 상하 관계(`regions.parent_id`), 주거 지원 사업 소식지(`support_programs`)와 검증 시드, 업체 계정 연결(`providers.account_user_id`), 요청인–업체 1:1 채팅(`chat_rooms`, `chat_messages`)과 방별 읽음 시각(`011`), 기록 지역 스냅샷(`012`), 업체 상세·평점(`013`), 견적 요청서·제안서와 사진 Storage 경로(`015`), 작업 종류 시드를 구현했다. 용인 실제 업체는 팀 확인 자료가 없어 `014` 템플릿만 두었다. 실제 업체 데이터와 보조금24 동기화 운영 데이터는 팀 확인·운영 작업이 남아 있다. 기존 마이그레이션으로 구현된 `questions`·`messages` 테이블과 `records.next_question_*` 컬럼은 분석 채팅창 제거 결정에 따라 **현재 MVP 미사용(보류/레거시)**으로 유지한다. 적용 SQL은 [마이그레이션](../../apps/api/migrations/), 실행·마이그레이션 절차는 [개발 환경·DB·테스트 가이드](../guides/DEVELOPMENT.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `apps/api/migrations/*.sql`과 `apps/api/app/migrate.py`가 마이그레이션을 담당한다. 적용 이력은 `schema_migrations`에 남는다.
- `records.owner_id`는 `auth.users(id)`를 외래키로 참조한다. 로컬 빈 DB에서는 `auth.users(id)` 스텁을 만들고, Supabase에서는 기존 테이블이 그대로 쓰인다.
- 질문·메시지 순서는 `records.conversation_sequence`에서 함께 발급한다. 각 테이블의 `(record_id, sequence)` 유일 제약은 유지하고, 두 테이블 사이의 순서는 기록 행 잠금과 같은 트랜잭션에서 조정한다. *(현재 MVP 미사용/보류)*
- `messages`는 `(record_id, question_id)` 복합 외래키로 같은 기록의 질문만 참조한다. `sender = 'user'`인 행은 `client_message_id`가 필수다. *(현재 MVP 미사용/보류)*
- `messages.input_revision`은 그 메시지가 반영된 뒤의 기록 입력 버전이다. *(현재 MVP 미사용/보류)*
- 런타임 역할 `career_pair_runtime`은 마이그레이션이 `NOLOGIN`으로 만들고 현재 구현된 API에 필요한 DML만 부여한다(기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/INSERT/UPDATE/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 프로필 `SELECT/INSERT/UPDATE`, 지원 사업 `SELECT/INSERT/UPDATE`, 채팅방·채팅 메시지 `SELECT/INSERT/UPDATE`, 업체·지역·작업 참조 테이블 `SELECT`). 업체 계정 연결에 필요한 `providers` UPDATE 권한은 런타임에 주지 않는다. 질문 INSERT/UPDATE는 `005_next_question_grants.sql`, `records.material`은 `006_records_material.sql`, `profiles`·용인 지역·기록 목록 인덱스는 `007_profiles_and_regions.sql`, 지역 상하 관계·지원 사업·시드는 `008_support_programs.sql`·`009_support_program_seed.sql`에서 추가한다. 기록의 테이블 단위 SELECT/UPDATE와 RLS 정책이 새 컬럼에도 적용되므로 별도 컬럼 권한은 추가하지 않는다. 동기화는 런타임 역할로 수행하며 지원 사업 DELETE 권한은 주지 않는다. 로그인 비밀번호는 관리자가 별도로 설정한다. 새 기능이 더 많은 권한을 필요로 하면 후속 마이그레이션에서 명시적으로 부여한다. Supabase Data API 역할(`anon`, `authenticated`, `service_role`)이 있으면 앱 테이블 권한과 향후 테이블 기본 권한을 회수한다.
- 앱 테이블에는 `003_backend_rls.sql`이 RLS를 켜고 `career_pair_runtime`만 통과시키는 정책을 둔다. Data API 역할은 권한 회수로 막고, 사용자별 접근 제어는 FastAPI의 소유권/참여자 검사로 수행한다.

## 테이블

| 테이블 | 상태 | 주요 컬럼 |
| --- | --- | --- |
| `profiles` | 구현됨 (`007`) | `user_id uuid PK/FK auth.users(id)`, `nickname text NOT NULL`, `role text NOT NULL`, `region_id uuid NOT NULL FK regions(id)`, `address text NULL`, `housing_type text NOT NULL`, `created_at timestamptz`, `updated_at timestamptz` |
| `records` | 구현됨 (`material`, 지역 스냅샷 `012`, 사진 `015`) | `id uuid PK`, `owner_id uuid`, `region_id uuid NULL FK regions(id)`, `photo_files jsonb NOT NULL DEFAULT '[]'`, `location text`, `material text NULL`, `symptoms text`, `photo_observations jsonb`, `input_revision bigint`, `next_question_result jsonb` *(레거시)*, `next_question_revision bigint` *(레거시)*, `diagnosis jsonb`, `diagnosis_revision bigint`, `diagnosis_generation bigint`, `landlord_draft text`, `landlord_draft_revision bigint`, `landlord_draft_diagnosis_generation bigint`, `provider_draft text`, `provider_draft_revision bigint`, `provider_draft_diagnosis_generation bigint`, `conversation_sequence bigint` *(레거시)*, `created_at timestamptz`, `updated_at timestamptz` |
| `support_programs` | 구현됨 (`008`·`009`·`017`) | `id uuid PK`, `external_id text UNIQUE NOT NULL`, `source text`(`seed`/`gov24_api`), `title`, `summary`, `organization_name`, `region_scope`(`national`/`local`), `region_id uuid NULL FK regions(id)`, `target_housing_types text[]`, `categories text[]`, `support_target`, `support_content`, `selection_criteria`, `apply_method`, `deadline_text`, `deadline_date date NULL`, `deadline_kind`(`fixed`/`always_open`/`unknown`), `detail_url`, `source_attribution`, `source_checked_at`, `synced_at`, `created_at`, `updated_at` |
| `providers` | 구현됨 (`010` 계정 연결, `013` 상세·평점) | `id uuid PK`, `name text NOT NULL`, `phone text NOT NULL`, `rating numeric(2,1) NOT NULL DEFAULT 0.0`, `review_count integer NOT NULL DEFAULT 0`, `description text NULL`, `address text NULL`, `business_hours text NULL`, `career_years integer NULL`, `account_user_id uuid NULL FK auth.users(id)` (`010`, NULL 제외 유일 인덱스) |
| `regions` | 구현됨 (`008`에서 상하 관계 추가) | `id uuid PK`, `name text NOT NULL UNIQUE`, `display_name text NOT NULL`, `parent_id uuid NULL FK regions(id)` |
| `work_types` | 구현됨 | `id uuid PK`, `name text NOT NULL UNIQUE` |
| `provider_regions` | 구현됨 | `provider_id uuid FK`, `region_id uuid FK` |
| `provider_work_types` | 구현됨 | `provider_id uuid FK`, `work_type_id uuid FK` |
| `quote_requests` | 구현됨 (`015`) | `id uuid PK`, `record_id uuid FK records(id)`, `requester_id uuid FK auth.users(id)`, `region_id uuid FK regions(id)`, `work_type_id uuid FK work_types(id)`, `address text NULL`, `location text NOT NULL`, `material text NULL`, `memo text NULL`, `photo_files jsonb`, `severity_score integer NULL`, `severity_level text NULL`, `suspected_types text[]`, `status text`(`open`/`accepted`/`cancelled`), `accepted_proposal_id uuid NULL FK quote_proposals(id)`, `accepted_at timestamptz NULL`, `created_at`, `updated_at` |
| `quote_proposals` | 구현됨 (`015`) | `id uuid PK`, `request_id uuid FK quote_requests(id)`, `provider_id uuid FK providers(id)`, `min_price integer`, `max_price integer`, `memo text`, `status text`(`pending`/`accepted`/`rejected`), `created_at`, `updated_at` |
| `chat_rooms` | 구현됨 (`010`, 읽음 시각 `011`) | `id uuid PK`, `requester_id uuid NOT NULL FK auth.users(id)`, `provider_id uuid NOT NULL FK providers(id)`, `latest_record_id uuid NULL FK records(id)`, `last_message_at timestamptz NULL`, `requester_last_read_at timestamptz NULL`, `provider_last_read_at timestamptz NULL`, `created_at timestamptz`, `updated_at timestamptz` |
| `chat_messages` | 구현됨 (`010`) | `id uuid PK`, `room_id uuid NOT NULL FK chat_rooms(id)`, `sender_id uuid NOT NULL FK auth.users(id)`, `sender_role text NOT NULL`, `message_type text NOT NULL`, `record_id uuid NULL FK records(id)`, `content text NOT NULL`, `payload jsonb NULL`, `client_message_id uuid NOT NULL`, `created_at timestamptz` |
| `questions` | 기존 구현 (MVP 미사용/보류) | `id uuid PK`, `record_id uuid FK`, `sequence bigint`, `content text`, `options jsonb`, `answered boolean`, `input_revision bigint`, `created_at timestamptz` |
| `messages` | 기존 구현 (MVP 미사용/보류) | `id uuid PK`, `record_id uuid FK`, `question_id uuid FK NULL`, `sequence bigint`, `sender text`, `content text`, `client_message_id uuid NULL`, `selected_option_id text NULL`, `submitted_content text NULL`, `input_revision bigint`, `created_at timestamptz` |

### `records`와 진단 저장 규칙

`owner_id`는 Supabase Auth의 사용자 ID를 참조한다. 새 기록에는 위치·재질·증상·분석·생성 결과가 아직 없을 수 있다. 생성 결과가 없으면 해당 값과 생성에 사용한 버전은 NULL이다. 사진 관찰 결과(`photo_observations`)에는 사진별 역할, 분석 적용 여부, 관찰한 흔적·의심 유형(`크랙`, `벗겨짐`, `곰팡이`)·대략적인 위치를 저장한다. 원본 이미지 파일과 화면 표시 좌표는 영구 저장하지 않는다.

샘플 일괄 분석은 `photo_observations`에 `source="sample"`, `applied=false`, 안내 문구, 사진별 역할과 `status="not_analyzed"`만 저장한다. 탐지 후보·신뢰도·bbox/좌표는 저장하지 않는다. `diagnosis`에는 구조화 진단과 `source="sample"`을 저장하고, `diagnosis_revision`은 입력 반영 후 버전, `diagnosis_generation`은 성공할 때마다 증가한 값을 기록한다. 원본 사진은 DB에 저장하지 않고, Storage 설정 시 비공개 버킷에 리사이즈 JPEG로 저장한다. FastAPI의 업로드 임시 파일은 성공·실패 모두 닫는다.

`diagnosis` JSONB는 `observations`, `suspected_types`(의심 하자 유형 목록), `severity_score`(`0`~`100` 또는 `null`), `severity_level`(`low`, `medium`, `high`, `undetermined`), `reason`, `causes`, `estimation_notice`, `recommended_action`(`self_care`, `inspection`, `provider_consult`), `care_steps`, `supplies`, `prevention_tips`, `unknowns`, `work_type_id`(샘플에서 `null` 가능), `work_type_reason`, `source`를 포함한다.

## 회원 프로필 (`profiles`, 구현 완료)

`profiles`는 회원 한 명의 닉네임, 역할, 현재 거주 지역, 선택 등록 주소, 거주 형태를 저장하는 테이블이다. `007_profiles_and_regions.sql`에서 추가했으며 `user_id`가 기본키다.

- `role`: `CHECK (role IN ('requester', 'provider'))`, 기본값 `'requester'`. FastAPI의 프로필 저장은 새 행을 `'requester'`로 만들고 기존 역할은 덮어쓰지 않는다. 일반 회원가입은 `'requester'`만 생성하며 시연용 업체 계정은 `'provider'`로 사전 등록한다.
- `nickname`: 공백만 입력할 수 없도록 `CHECK (length(btrim(nickname)) > 0)`.
- `region_id`: `regions(id)` 참조 (`NOT NULL`). `007`은 시연 지역 용인(`name='yongin'`, `display_name='경기도 용인시'`)을 `ON CONFLICT (name) DO NOTHING`으로 시드한다.
- `address`: 선택 입력 (`text NULL`). 상세 등록 주소를 계속 유지할지 거주 지역만 수집할지는 팀 추가 논의 항목이다.
- `housing_type`: `CHECK (housing_type IN ('monthly_rent', 'jeonse', 'semi_jeonse', 'owned', 'other'))` (`월세`, `전세`, `반전세`, `자가`, `기타`).
- `updated_at`: 프로필을 저장할 때 서버가 갱신한다.

계정 생성과 프로필 저장은 별도 단계이며, `PUT /me/profile`은 같은 사용자 ID로 upsert해 저장 실패 후 재시도해도 한 행만 유지한다. 프로필이 없는 기존 계정에는 프로필 등록을 안내한다. 상세 주소를 외부 AI 모델 입력에 자동 포함하지 않으며, 프로필 갱신으로 과거 기록과 요청문을 일괄 수정하지 않는다.

## 소식지 (`support_programs`, 구현 완료)

`support_programs`는 주거 관련 정부·지자체 지원 사업과 공고를 저장하는 테이블이다. `008_support_programs.sql`이 테이블·제약·인덱스·RLS·런타임 권한을 만들고, `009_support_program_seed.sql`이 2026-11-20에 공식 원문으로 확인한 시드 4건을 넣는다. 시드는 `external_id`가 `seed:`로 시작하고 `ON CONFLICT (external_id) DO NOTHING`이라 반복 적용해도 중복되지 않는다.

- `external_id`: 보조금24 API의 `서비스ID` 또는 시드의 고정 ID. `UNIQUE`, upsert 기준이다.
- `source`: `CHECK (source IN ('seed', 'gov24_api'))`.
- `region_scope`: `CHECK (region_scope IN ('national', 'local'))`. `national`은 `region_id IS NULL`, `local`은 `region_id IS NOT NULL`이어야 한다.
- `region_id`: `regions(id)` 참조. `regions.parent_id`로 상위 지역을 표현하며, `008`은 경기도(`gyeonggi`)를 추가하고 용인시(`yongin`)의 상위로 연결한다. 기존 부모 관계가 있으면 덮어쓰지 않는다.
- `target_housing_types`: `monthly_rent`, `jeonse`, `semi_jeonse`, `owned`, `other`만 허용하는 `text[]`. 공고 원문에 명시된 거주 형태만 태그하며, 태그가 신청 자격을 확정하지 않는다.
- `categories`: 제목·요약 키워드로 분류한 참고 카테고리 `text[]`. `monthly_rent_support`, `deposit_loan`, `housing_cost`, `repair`, `brokerage_fee`, `supply`, `other`만 허용하며 비어 있을 수 없다. 한 공고가 여러 카테고리에 속할 수 있고, 신청 자격을 확정하지 않는다. `017_support_program_categories.sql`이 컬럼·CHECK·시드 백필을 추가한다.
- `support_target`·`support_content`: 공식 원문의 지원 대상과 지원 내용. 동기화에서 비어 있으면 해당 행을 저장하지 않는다.
- `selection_criteria`·`apply_method`: 원문에 있을 때만 저장하며 없으면 `NULL`이다.
- `deadline_text`: 공식 신청기한 원문(없으면 `NULL`). `deadline_date`: 명확히 해석한 마감일만 저장하고, `deadline_kind`는 `fixed`·`always_open`·`unknown` 중 하나다. 동기화는 `신청기한유형`을 우선 사용해 `상시신청`을 `always_open`, `기간설정`의 단일 기간을 `fixed`, `접수기관별상이`·모호한 `직접입력`을 `unknown`으로 둔다. `fixed`는 날짜가 필수이고 나머지는 날짜가 `NULL`이어야 한다. 마감일 당일은 마감으로 처리하지 않고 한국 시간 기준 다음 날부터 `is_closed=true`가 된다.
- `detail_url`: 공식 원문 URL. `http`·`https`만 허용하는 DB CHECK가 있다.
- `source_attribution`: 화면에 표시할 출처. 보조금24 동기화는 `행정안전부 대한민국 공공서비스(혜택) 정보 · 공공데이터포털`, 시드는 각 공식 원문 기관을 기록한다.
- `source_checked_at`: 출처를 마지막으로 확인한 시각. `synced_at`: 외부 API에서 마지막으로 갱신한 시각(시드는 `NULL`).
- `created_at`·`updated_at`: 생성·갱신 시각.

시드 데이터 계약은 다음 네 건이다. 공고명·마감·URL은 공식 원문에서 확인한 범위만 넣었고, 확인되지 않은 마감은 `NULL`/`unknown`으로 보존한다.

| `external_id` | 범위 | 공식 원문 |
| --- | --- | --- |
| `seed:gov24-youth-monthly-rent-2026` | 전국 · 국토교통부 | [복지로 청년월세 지원사업](https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004661) |
| `seed:gyeonggi-independent-youth-housing-2026` | 경기도 · 경기주택도시공사 | [경기청년포털 자립준비청년 주거비 지원사업](https://youth.gg.go.kr/gg/intro/youth-policy-educational-testing.do?articleNo=9010&mode=view) |
| `seed:yongin-youth-brokerage-fee-2026` | 용인시 | [용인청년포털 부동산 중개보수 감면](https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026021000000000000055001) |
| `seed:yongin-youth-monthly-rent-2026` | 용인시 | [용인청년포털 청년월세 지원](https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026032300000000000061001) |

보조금24 동기화는 `serviceList`의 `서비스ID`, `서비스명`, `서비스목적요약`, `소관기관명`, `소관기관유형`, `지원대상`, `지원내용`, `신청방법`, `신청기한`, `신청기한유형`, `상세조회URL`을 사용한다. 서비스명에 주거 관련 키워드가 있는 사업만 반영한다. `소관기관명`이 등록 지역 표시명과 정확히 일치할 때만 `local`로 확정하고, 중앙행정기관은 `national`로만 분류한다. 시·군·구명이 다르거나 모호한 지역은 저장하지 않는다. 거주 형태는 원문에 명시된 경우만 태그하고, 카테고리는 제목·요약 키워드로만 분류한다. 검증 시드와 같은 제목(끝의 `사업` 제외)·기관·지역의 API 행은 목록에서 시드로 대체한다.

## 업체–요청인 1:1 채팅 (`chat_rooms`, `chat_messages`, 구현 완료)

기존 AI 추가 질문용 `questions`·`messages` 테이블을 재사용하지 않고, 요청인–업체 상담 전용 테이블을 분리했다. `010_chat_and_provider_accounts.sql`이 방·메시지를, `011_chat_read_state.sql`이 참여자별 읽음 시각 컬럼을 만든다.

- `providers.account_user_id`: 사전 등록된 업체 계정(`auth.users.id`)과 1:1 연결한다. `ON DELETE SET NULL`이며 `WHERE account_user_id IS NOT NULL` 부분 유일 인덱스(`providers_account_user_id_key`)로 같은 계정을 두 업체에 연결할 수 없다. 연결은 관리자 SQL로만 하고 런타임 API에는 공개하지 않는다.
- `chat_rooms`: `UNIQUE (requester_id, provider_id)`로 동일 요청인·업체 조합당 하나의 채팅방을 유지·재사용한다. 동시 생성은 이 제약에서 하나로 수렴한다. `latest_record_id`는 가장 최근 공유된 하자 기록을 가리킨다(`ON DELETE SET NULL`). `last_message_at`은 마지막 메시지 시각이다.
- `chat_rooms.requester_last_read_at`, `provider_last_read_at`: 참여자별 마지막 읽음 시각(`011`). `POST /chat/rooms/{room_id}/read`가 서버 `now()`로 갱신한다. 미읽음 수는 이 시각 이후에 생성된 상대방 메시지를 세며, `NULL`이면 상대방 메시지 전체가 미읽음이다. 같은 계정의 기기 간 동기화는 이 서버 값으로 이뤄진다.
- `chat_messages`:
  - `sender_role`: `CHECK (sender_role IN ('requester', 'provider'))`
  - `message_type`: `CHECK (message_type IN ('text', 'record_summary'))`
  - `record_id`: 분석 결과 요약 메시지일 때 연결된 `records(id)` (`ON DELETE SET NULL`)
  - `payload`: `record_summary` 메시지일 때 의심 유형, 위치, 재질, 심각도%, 추정 원인, 진단 버전 스냅샷을 담는 `jsonb`(객체만 허용)
  - `content`: 공백 제거 후 비어 있지 않고 2000자 이하
  - `client_message_id`: `UNIQUE (room_id, client_message_id)`로 REST 재전송 중복을 막는다. 서버가 만드는 요약 메시지는 서버가 UUID를 발급한다.
- 원본 기록·프로필 접근은 부여하지 않는다. 업체는 공유된 `payload`·`content`만 읽고, `records`·`profiles` 조회는 FastAPI 소유권 검사로 막힌다.

## 권한 및 RLS 정책

- `profiles`, `support_programs`, `chat_rooms`, `chat_messages` 모두 기존 앱 테이블과 동일하게 Supabase Data API(`anon`, `authenticated`, `service_role`) 권한을 회수하고, `career_pair_runtime` 역할만 필요한 DML 권한을 부여해 RLS를 통과시키는 구조를 기본으로 둔다.
  - `profiles`(구현 완료): `SELECT, INSERT, UPDATE`
  - `support_programs`(구현 완료): `SELECT, INSERT, UPDATE` (동기화 upsert용, DELETE 없음)
  - `chat_rooms`, `chat_messages`(구현 완료, `010`; 읽음 컬럼 `011`): `SELECT, INSERT, UPDATE` (DELETE 없음). `011`은 테이블 권한을 바꾸지 않으므로 기존 `UPDATE`로 읽음 시각을 갱신한다.
  - `quote_requests`, `quote_proposals`(구현 완료, `015`): `SELECT, INSERT, UPDATE` (DELETE 없음). 요청서당 공개 1건·수락 1건, 업체당 제안 1건은 유일 인덱스·제약으로 강제한다.
  - `providers`(구현 완료): `SELECT`만. 상세·평점 컬럼(`013`)도 읽기만 가능하며, 계정 연결·평점 갱신은 관리자 SQL/향후 서버 절차로 수행한다.
- 실시간 수신은 **FastAPI WebSocket**으로 확정했으므로 Supabase Data API(`authenticated`)에 채팅 테이블을 노출하지 않는다. 참여자 검사는 FastAPI가 REST와 WebSocket 인증 모두에서 수행한다. 푸시 알림은 추가하지 않는다.

## 제약과 인덱스

- `quote_requests(record_id) WHERE status='open'` 부분 유일 인덱스, `(region_id, work_type_id, status, created_at DESC)`, `(requester_id, created_at DESC)` 인덱스를 둔다. `quote_proposals(request_id, provider_id)` 유일 제약과 `(request_id) WHERE status='accepted'` 부분 유일 인덱스로 수락 1건을 DB에서 강제한다.
- `providers(rating DESC, review_count DESC, name, id)` 인덱스로 별점순 추천 정렬을 지원한다. `013_provider_details.sql`에서 추가했다.
- `records(region_id)` 부분 인덱스(`WHERE region_id IS NOT NULL`)를 두어 향후 지역 기반 요청서 매칭을 지원한다. `012_records_region.sql`에서 추가했다.
- `records(owner_id)` 및 `(owner_id, updated_at DESC)`에 인덱스를 두어 `내 정보`의 내 하자 분석 기록 목록 조회를 지원한다. `(owner_id, updated_at DESC)` 인덱스는 `007_profiles_and_regions.sql`에서 추가했다.
- `profiles(region_id)` 인덱스를 두어 지역별 조회를 지원한다. `007_profiles_and_regions.sql`에서 추가했다.
- `support_programs(region_scope, region_id, deadline_date)` 인덱스와 `(source, synced_at DESC)` 인덱스로 지역 필터·마감 정렬·동기화 상태를 지원한다. `008_support_programs.sql`에서 추가했다.
- `regions(parent_id)` 인덱스로 상위 지역 조회를 지원한다. `008_support_programs.sql`에서 추가했다.
- `chat_rooms(requester_id, provider_id)` 유일 제약과 `chat_rooms(requester_id, last_message_at DESC)`, `chat_rooms(provider_id, last_message_at DESC)` 인덱스를 둔다.
- `chat_messages(room_id, client_message_id)` 유일 제약과 `chat_messages(room_id, created_at, id)` 인덱스를 둔다.
- 사진 객체는 DB가 아니라 Supabase Storage 비공개 버킷(`defect-photos`)에 두고, `records.photo_files`에는 `role`·`storage_path`·`width`·`height`만 저장한다.
- `work_types`는 `010`이 `곰팡이 제거`, `균열 보수`, `벽지·도장 보수`, `원인 점검`을 `ON CONFLICT (name) DO NOTHING`으로 시드한다. `014_yongin_provider_seed.sql`은 공식 출처로 확인한 용인 업체를 고정 UUID와 `ON CONFLICT (id) DO NOTHING`으로 입력하는 템플릿이며, 팀 확인 자료가 없어 실제 행은 넣지 않았다.
- 업체와 지역, 업체와 작업 연결은 각각 두 ID를 복합 기본키로 사용하고, 지역 ID·작업 ID 역방향 인덱스를 유지한다.
- *(레거시/보류)* `messages(record_id, client_message_id)`, `questions(record_id, sequence)`, `messages(record_id, sequence)` 및 `(record_id, question_id)` 복합 외래키는 기존 마이그레이션에 유지한다.

## 갱신 규칙

입력(`location`, `material`, `symptoms`, 저장된 사진 관찰) 변경 시 기록 행을 잠근 트랜잭션에서 현재 입력 버전을 확인하고, 변경과 버전 증가를 함께 처리한다. 생성 결과 저장 시 생성에 사용한 버전과 현재 버전을 비교한다.

샘플 일괄 분석은 입력 스냅샷으로 결과를 만든 뒤 저장 직전에 기록 행을 다시 잠근다. 입력 버전이 바뀌었으면 아무것도 저장하지 않고 409를 반환한다. 제출한 위치·재질·증상이 실제로 달라질 때만 `input_revision`을 1 올리고, `photo_observations`(샘플 상태), `diagnosis`, `diagnosis_revision`, 증가한 `diagnosis_generation`을 같은 트랜잭션에 저장한다. 같은 입력이면 버전은 유지하고 생성 번호만 올린다. 사진 원본과 표시 좌표는 어느 경로에서도 저장하지 않는다.

진단의 최신 여부는 생성에 사용한 입력 버전으로 판단한다. 진단 저장 성공 시 `diagnosis_generation`을 증가시킨다. 요청문은 생성에 사용한 입력 버전과 진단 생성 번호가 모두 현재 값과 일치해야 최신이다. 요청문 저장 직전에도 두 값을 트랜잭션에서 검사한다. 진단 재생성 실패 시 생성 번호와 기존 결과를 유지한다. 현재 버전 결과는 재사용하며, 명시적인 재생성만 모델을 다시 호출한다. 실패한 생성으로 기존 값을 덮어쓰지 않는다.

샘플 업체는 실제 업체 테이블(`providers`)에 섞어 넣지 않고 검색 API가 빈 결과일 때 반환한다. 수정한 요청문은 앱의 현재 화면에서만 유지한다.

## 구현 전 확인

- 회원가입 `등록 주소` 유지 여부 vs `거주 지역`만 수집
- 설문/객관식 추가 질문 추후 도입 여부 (현재 보류)
- 업체–요청인 채팅 푸시 알림 도입 여부(WebSocket·읽음 처리는 구현 완료, 읽음 시점은 방 이력 조회 직후로 확정)
- `크랙·벗겨짐·곰팡이`별 심각도(%) 기준과 YOLO → 비전 LLM 2차 분석 호출 기준
- 용인시 시연용 실제 업체·계정 데이터 및 검색 지역·작업 목록
- 개인정보 보관 범위와 보유기간, 외부 DB 서비스에 적용되는 대회 규정의 범위
