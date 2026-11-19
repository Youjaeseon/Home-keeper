# MVP DB 설계 초안

합의한 저장 규칙을 기준으로 정리한 테이블 설계다. 아래 테이블 표는 전체 설계 요약이며, 현재 실제 DB에 적용된 컬럼·타입은 초기 마이그레이션(`001`–`005`)과 구현 확정 사항을 함께 확인한다. 접근·생성·실패 처리 규칙은 [백엔드 설계](BACKEND_DESIGN.md)를 따른다.

## 문서 범위

아래 구현 확정 사항은 현재 마이그레이션(`001`–`005`)에 반영된 내용이다.

2026년 11월 20일 팀 회의 변경 사항을 반영해 `profiles`(닉네임·역할·거주 지역·선택 등록 주소·거주 형태), `records.material`, `providers.account_user_id`, `support_programs`(소식지 주거 지원 사업), `chat_rooms`, `chat_messages`(업체–요청인 1:1 채팅) 추가를 후속 마이그레이션 대상으로 설계했다. 기존 마이그레이션으로 구현된 `questions`·`messages` 테이블과 `records.next_question_*` 컬럼은 분석 채팅창 제거 결정에 따라 **현재 MVP 미사용(보류/레거시)**으로 유지한다. 적용 SQL은 [마이그레이션](../../apps/api/migrations/), 실행 방법은 [README](../../README.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `apps/api/migrations/*.sql`과 `apps/api/app/migrate.py`가 마이그레이션을 담당한다. 적용 이력은 `schema_migrations`에 남는다.
- `records.owner_id`는 `auth.users(id)`를 외래키로 참조한다. 로컬 빈 DB에서는 `auth.users(id)` 스텁을 만들고, Supabase에서는 기존 테이블이 그대로 쓰인다.
- 질문·메시지 순서는 `records.conversation_sequence`에서 함께 발급한다. 각 테이블의 `(record_id, sequence)` 유일 제약은 유지하고, 두 테이블 사이의 순서는 기록 행 잠금과 같은 트랜잭션에서 조정한다. *(현재 MVP 미사용/보류)*
- `messages`는 `(record_id, question_id)` 복합 외래키로 같은 기록의 질문만 참조한다. `sender = 'user'`인 행은 `client_message_id`가 필수다. *(현재 MVP 미사용/보류)*
- `messages.input_revision`은 그 메시지가 반영된 뒤의 기록 입력 버전이다. *(현재 MVP 미사용/보류)*
- 런타임 역할 `career_pair_runtime`은 마이그레이션이 `NOLOGIN`으로 만들고 현재 구현된 API에 필요한 DML만 부여한다(기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/INSERT/UPDATE/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 업체·지역·작업 참조 테이블 `SELECT`). 질문 INSERT/UPDATE는 `005_next_question_grants.sql`에서 추가한다. 로그인 비밀번호는 관리자가 별도로 설정한다. 새 기능이 더 많은 권한을 필요로 하면 후속 마이그레이션에서 명시적으로 부여한다. Supabase Data API 역할(`anon`, `authenticated`, `service_role`)이 있으면 앱 테이블 권한과 향후 테이블 기본 권한을 회수한다.
- 앱 테이블에는 `003_backend_rls.sql`이 RLS를 켜고 `career_pair_runtime`만 통과시키는 정책을 둔다. Data API 역할은 권한 회수로 막고, 사용자별 접근 제어는 FastAPI의 소유권/참여자 검사로 수행한다.

## 테이블

| 테이블 | 상태 | 주요 컬럼 |
| --- | --- | --- |
| `profiles` | 구현 예정 | `user_id uuid PK/FK auth.users(id)`, `nickname text NOT NULL`, `role text NOT NULL`, `region_id uuid NOT NULL FK regions(id)`, `address text NULL`, `housing_type text NOT NULL`, `created_at timestamptz`, `updated_at timestamptz` |
| `records` | 구현됨 (`material` 추가 예정) | `id uuid PK`, `owner_id uuid`, `location text`, `material text NULL` *(추가 예정)*, `symptoms text`, `photo_observations jsonb`, `input_revision bigint`, `next_question_result jsonb` *(레거시)*, `next_question_revision bigint` *(레거시)*, `diagnosis jsonb`, `diagnosis_revision bigint`, `diagnosis_generation bigint`, `landlord_draft text`, `landlord_draft_revision bigint`, `landlord_draft_diagnosis_generation bigint`, `provider_draft text`, `provider_draft_revision bigint`, `provider_draft_diagnosis_generation bigint`, `conversation_sequence bigint` *(레거시)*, `created_at timestamptz`, `updated_at timestamptz` |
| `support_programs` | 구현 예정 | `id uuid PK`, `external_id text UNIQUE NULL`, `source text NOT NULL`, `title text NOT NULL`, `summary text NOT NULL`, `organization_name text NOT NULL`, `region_scope text NOT NULL`, `region_id uuid NULL FK regions(id)`, `target_housing_types text[]`, `deadline_text text NOT NULL`, `deadline_date date NULL`, `apply_method text NULL`, `detail_url text NULL`, `source_attribution text NOT NULL`, `synced_at timestamptz NULL`, `created_at timestamptz`, `updated_at timestamptz` |
| `providers` | 구현됨 (`account_user_id` 추가 예정) | `id uuid PK`, `name text NOT NULL`, `phone text NOT NULL`, `account_user_id uuid NULL UNIQUE FK auth.users(id)` *(추가 예정)* |
| `regions` | 구현됨 | `id uuid PK`, `name text NOT NULL UNIQUE`, `display_name text NOT NULL` |
| `work_types` | 구현됨 | `id uuid PK`, `name text NOT NULL UNIQUE` |
| `provider_regions` | 구현됨 | `provider_id uuid FK`, `region_id uuid FK` |
| `provider_work_types` | 구현됨 | `provider_id uuid FK`, `work_type_id uuid FK` |
| `chat_rooms` | 구현 예정 | `id uuid PK`, `requester_id uuid NOT NULL FK auth.users(id)`, `provider_id uuid NOT NULL FK providers(id)`, `latest_record_id uuid NULL FK records(id)`, `last_message_at timestamptz NULL`, `created_at timestamptz`, `updated_at timestamptz` |
| `chat_messages` | 구현 예정 | `id uuid PK`, `room_id uuid NOT NULL FK chat_rooms(id)`, `sender_id uuid NOT NULL FK auth.users(id)`, `sender_role text NOT NULL`, `message_type text NOT NULL`, `record_id uuid NULL FK records(id)`, `content text NOT NULL`, `payload jsonb NULL`, `client_message_id uuid NOT NULL`, `created_at timestamptz` |
| `questions` | 기존 구현 (MVP 미사용/보류) | `id uuid PK`, `record_id uuid FK`, `sequence bigint`, `content text`, `options jsonb`, `answered boolean`, `input_revision bigint`, `created_at timestamptz` |
| `messages` | 기존 구현 (MVP 미사용/보류) | `id uuid PK`, `record_id uuid FK`, `question_id uuid FK NULL`, `sequence bigint`, `sender text`, `content text`, `client_message_id uuid NULL`, `selected_option_id text NULL`, `submitted_content text NULL`, `input_revision bigint`, `created_at timestamptz` |

### `records`와 진단 저장 규칙

`owner_id`는 Supabase Auth의 사용자 ID를 참조한다. 새 기록에는 위치·재질·증상·분석·생성 결과가 아직 없을 수 있다. 생성 결과가 없으면 해당 값과 생성에 사용한 버전은 NULL이다. 사진 관찰 결과(`photo_observations`)에는 사진별 역할, 분석 적용 여부, 관찰한 흔적·의심 유형(`크랙`, `벗겨짐`, `곰팡이`)·대략적인 위치를 저장한다. 원본 이미지 파일과 화면 표시 좌표는 영구 저장하지 않는다.

`diagnosis` JSONB는 `observations`, `severity_score`(`0`~`100` 또는 `null`), `severity_level`(`low`, `medium`, `high`, `undetermined`), `reason`, `causes`, `estimation_notice`, `recommended_action`(`self_care`, `inspection`, `provider_consult`), `care_steps`, `supplies`, `prevention_tips`, `unknowns`, `work_type_id`, `work_type_reason`을 포함한다.

## 회원 프로필 추가 설계 (`profiles`, 구현 예정)

`profiles`는 회원 한 명의 닉네임, 역할, 현재 거주 지역, 선택 등록 주소, 거주 형태를 저장할 예정인 테이블이다. 기존 마이그레이션(`001`–`005`)에는 없으며 후속 마이그레이션으로 추가한다.

- `role`: `CHECK (role IN ('requester', 'provider'))`, 기본값 `'requester'`. 일반 회원가입은 `'requester'`만 생성하며 시연용 업체 계정은 `'provider'`로 사전 등록한다.
- `region_id`: `regions(id)` 참조 (`NOT NULL`).
- `address`: 선택 입력 (`text NULL`). 상세 등록 주소를 계속 유지할지 거주 지역만 수집할지는 팀 추가 논의 항목이다.
- `housing_type`: `CHECK (housing_type IN ('monthly_rent', 'jeonse', 'semi_jeonse', 'owned', 'other'))` (`월세`, `전세`, `반전세`, `자가`, `기타`).

계정 생성과 프로필 저장은 별도 단계이며, 저장 실패 시 같은 사용자 ID로 다시 저장한다. 프로필이 없는 기존 계정에는 프로필 등록을 안내한다. 상세 주소를 외부 AI 모델 입력에 자동 포함하지 않으며, 프로필 갱신으로 과거 기록과 요청문을 일괄 수정하지 않는다.

## 소식지 추가 설계 (`support_programs`, 구현 예정)

`support_programs`는 주거 관련 정부·지자체 지원 사업을 저장할 테이블이다.

- `external_id`: 보조금24 API의 서비스 ID(`SVC_ID`, `UNIQUE NULL`). API 동기화 시 upsert 기준 키로 사용한다.
- `source`: `CHECK (source IN ('gov24_api', 'seed'))`.
- `region_scope`: `CHECK (region_scope IN ('national', 'local'))`. `national`일 때는 `region_id`가 `NULL`, `local`일 때는 `regions(id)`를 참조할 수 있다.
- `target_housing_types`: `text[] NOT NULL DEFAULT '{}'`. 사용자 `housing_type`과 겹치는 사업을 우선 표시·태그하는 데 사용한다.
- `deadline_text` / `deadline_date`: 보조금24 API의 자유 텍스트 `신청기한` 원문을 `deadline_text`에 저장하고, 날짜 파싱 또는 시드 입력 시 `deadline_date`(`date NULL`)를 함께 저장한다. `deadline_date < CURRENT_DATE`인 공고만 마감으로 판정한다.
- `source_attribution`: 공공누리(KOGL) 기준에 따른 출처 표시 문자열(예: `행정안전부 공공서비스(혜택) 정보 · 공공데이터포털`).

## 업체–요청인 1:1 채팅 추가 설계 (`chat_rooms`, `chat_messages`, 구현 예정)

기존 AI 추가 질문용 `questions`·`messages` 테이블을 재사용하지 않고, 요청인–업체 상담 전용 테이블을 분리해 신설한다.

- `providers.account_user_id`: 사전 등록된 시연용 업체 계정(`auth.users.id`)과 1:1 연결한다(`UNIQUE NULL`).
- `chat_rooms`: `UNIQUE (requester_id, provider_id)`로 동일 요청인·업체 조합당 하나의 채팅방을 유지·재사용한다. `latest_record_id`는 가장 최근 공유된 하자 기록을 가리킨다(`ON DELETE SET NULL`).
- `chat_messages`:
  - `sender_role`: `CHECK (sender_role IN ('requester', 'provider'))`
  - `message_type`: `CHECK (message_type IN ('text', 'record_summary'))`
  - `record_id`: 분석 결과 요약 메시지일 때 연결된 `records(id)` (`ON DELETE SET NULL`)
  - `payload`: `record_summary` 메시지일 때 의심 유형, 위치, 재질, 심각도%, 추정 원인 스냅샷을 담는 `jsonb NULL`
  - `client_message_id`: `UNIQUE (room_id, client_message_id)`로 REST 재전송 시 중복 저장을 방지한다.

## 권한 및 RLS 정책

- `profiles`, `support_programs`, `chat_rooms`, `chat_messages` 모두 기존 앱 테이블과 동일하게 Supabase Data API(`anon`, `authenticated`, `service_role`) 권한을 회수하고, `career_pair_runtime` 역할만 필요한 DML 권한을 부여해 RLS를 통과시키는 구조를 기본으로 둔다.
  - `profiles`: `SELECT, INSERT, UPDATE`
  - `support_programs`: `SELECT, INSERT, UPDATE` (동기화 작업 시 백엔드 갱신 허용)
  - `chat_rooms`, `chat_messages`: `SELECT, INSERT, UPDATE`
- *(예외 참고)* 만약 팀원 협의 결과 채팅 실시간 수신 방식으로 `Supabase Realtime`을 채택한다면, `chat_rooms`와 `chat_messages`에 한해 `authenticated` 참여자 본인만 조회할 수 있는 예외 RLS 정책을 별도로 검토해야 한다. `FastAPI REST 폴링` 또는 `FastAPI WebSocket`을 선택하면 기존 Data API 차단 경계를 그대로 유지한다.

## 제약과 인덱스

- `records(owner_id)` 및 `(owner_id, updated_at DESC)`에 인덱스를 두어 `내 정보`의 내 하자 분석 기록 목록 조회를 지원한다.
- `support_programs(region_scope, region_id, deadline_date)`에 인덱스를 두어 거주 지역+전국 필터링과 마감 하단 정렬을 지원한다.
- `chat_rooms(requester_id, provider_id)` 유일 제약과 `chat_rooms(requester_id, last_message_at DESC)`, `chat_rooms(provider_id, last_message_at DESC)` 인덱스를 둔다.
- `chat_messages(room_id, client_message_id)` 유일 제약과 `chat_messages(room_id, created_at, id)` 인덱스를 둔다.
- 업체와 지역, 업체와 작업 연결은 각각 두 ID를 복합 기본키로 사용하고, 지역 ID·작업 ID 역방향 인덱스를 유지한다.
- *(레거시/보류)* `messages(record_id, client_message_id)`, `questions(record_id, sequence)`, `messages(record_id, sequence)` 및 `(record_id, question_id)` 복합 외래키는 기존 마이그레이션에 유지한다.

## 갱신 규칙

입력(`location`, `material`, `symptoms`, 저장된 사진 관찰) 변경 시 기록 행을 잠근 트랜잭션에서 현재 입력 버전을 확인하고, 변경과 버전 증가를 함께 처리한다. 생성 결과 저장 시 생성에 사용한 버전과 현재 버전을 비교한다.

진단의 최신 여부는 생성에 사용한 입력 버전으로 판단한다. 진단 저장 성공 시 `diagnosis_generation`을 증가시킨다. 요청문은 생성에 사용한 입력 버전과 진단 생성 번호가 모두 현재 값과 일치해야 최신이다. 요청문 저장 직전에도 두 값을 트랜잭션에서 검사한다. 진단 재생성 실패 시 생성 번호와 기존 결과를 유지한다. 현재 버전 결과는 재사용하며, 명시적인 재생성만 모델을 다시 호출한다. 실패한 생성으로 기존 값을 덮어쓰지 않는다.

샘플 업체는 실제 업체 테이블(`providers`)에 섞어 넣지 않고 검색 API가 빈 결과일 때 반환한다. 수정한 요청문은 앱의 현재 화면에서만 유지한다.

## 구현 전 확인

- 회원가입 `등록 주소` 유지 여부 vs `거주 지역`만 수집
- 설문/객관식 추가 질문 추후 도입 여부 (현재 보류)
- 업체–요청인 채팅 실시간 전송 방식(REST 폴링 / WebSocket / Supabase Realtime) 및 업체 화면 구성
- `크랙·벗겨짐·곰팡이`별 심각도(%) 기준과 YOLO → 비전 LLM 2차 분석 호출 기준
- 용인시 시연용 실제 업체·계정 데이터 및 검색 지역·작업 목록
- 개인정보 보관 범위와 보유기간, 외부 DB 서비스에 적용되는 대회 규정의 범위
