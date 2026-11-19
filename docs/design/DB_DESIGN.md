# MVP DB 설계 초안

합의한 저장 규칙을 기준으로 정리한 테이블 초안이다. 아래 테이블 표는 설계 요약이며, 적용된 컬럼과 타입은 초기 마이그레이션과 구현 확정 사항을 함께 확인한다. 접근·생성·실패 처리 규칙은 [백엔드 설계](BACKEND_DESIGN.md)를 따른다.

## 문서 범위

아래 구현 확정 사항은 현재 마이그레이션에 반영된 내용이다. 시연용 다음 질문은 기존 컬럼을 사용하고, 진단과 요청문 등 후속 기능의 저장 컬럼도 준비되어 있으며 해당 생성 API는 후속 구현 대상이다. 적용 SQL은 [마이그레이션](../../apps/api/migrations/), 실행 방법은 [README](../../README.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `apps/api/migrations/*.sql`과 `apps/api/app/migrate.py`가 마이그레이션을 담당한다. 적용 이력은 `schema_migrations`에 남는다.
- `records.owner_id`는 `auth.users(id)`를 외래키로 참조한다. 로컬 빈 DB에서는 `auth.users(id)` 스텁을 만들고, Supabase에서는 기존 테이블이 그대로 쓰인다.
- 질문·메시지 순서는 `records.conversation_sequence`에서 함께 발급한다. 각 테이블의 `(record_id, sequence)` 유일 제약은 유지하고, 두 테이블 사이의 순서는 기록 행 잠금과 같은 트랜잭션에서 조정한다.
- `messages`는 `(record_id, question_id)` 복합 외래키로 같은 기록의 질문만 참조한다. `sender = 'user'`인 행은 `client_message_id`가 필수다.
- `messages.input_revision`은 그 메시지가 반영된 뒤의 기록 입력 버전이다. 과거 메시지를 수정하면 수정된 메시지의 버전도 새 기록 버전으로 바꾼다.
- 런타임 역할 `career_pair_runtime`은 마이그레이션이 `NOLOGIN`으로 만들고 이번 API에 필요한 DML만 부여한다(기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/INSERT/UPDATE/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 업체·지역·작업 참조 테이블 `SELECT`). 질문 INSERT/UPDATE는 `005_next_question_grants.sql`에서 추가한다. 로그인 비밀번호는 관리자가 별도로 설정한다. 새 기능이 더 많은 권한을 필요로 하면 새 마이그레이션에서 부여한다. Supabase Data API 역할(`anon`, `authenticated`, `service_role`)이 있으면 앱 테이블 권한과 향후 테이블 기본 권한을 회수한다.
- 앱 테이블에는 `003_backend_rls.sql`이 RLS를 켜고 `career_pair_runtime`만 통과시키는 정책을 둔다. Data API 역할은 권한 회수로 막고, 사용자별 접근 제어는 FastAPI의 소유권 검사로 수행한다.

## 테이블

| 테이블 | 주요 컬럼 |
| --- | --- |
| `records` | `id uuid PK`, `owner_id uuid`, `location text`, `symptoms text`, `photo_observations jsonb`, `input_revision bigint`, `next_question_result jsonb`, `next_question_revision bigint`, `diagnosis jsonb`, `diagnosis_revision bigint`, `diagnosis_generation bigint`, `landlord_draft text`, `landlord_draft_revision bigint`, `landlord_draft_diagnosis_generation bigint`, `provider_draft text`, `provider_draft_revision bigint`, `provider_draft_diagnosis_generation bigint`, 생성·수정 시각 |
| `questions` | `id uuid PK`, `record_id uuid FK`, `sequence bigint`, `content text`, `options jsonb`, `answered boolean`, `input_revision bigint`, 생성 시각 |
| `messages` | `id uuid PK`, `record_id uuid FK`, `question_id uuid FK NULL`, `sequence bigint`, `sender text`, `content text`, `client_message_id uuid NULL`, `selected_option_id text NULL`, `submitted_content text NULL`, `input_revision bigint`, 생성 시각 |
| `providers` | `id uuid PK`, `name text`, `phone text` |
| `regions` | `id uuid PK`, `name text`, `display_name text` |
| `work_types` | `id uuid PK`, `name text` |
| `provider_regions` | `provider_id uuid FK`, `region_id uuid FK` |
| `provider_work_types` | `provider_id uuid FK`, `work_type_id uuid FK` |

`owner_id`는 Supabase Auth의 사용자 ID를 참조한다. 새 기록에는 위치·증상·분석·생성 결과가 아직 없을 수 있다. 생성 결과가 없으면 해당 값과 생성에 사용한 버전은 NULL이다. 사진 관찰 결과에는 사진별 역할과 관찰한 흔적·유형·대략적인 위치를 저장한다. 이미지 파일과 표시 좌표는 저장하지 않는다.

선택지는 질문 안에서 유일한 `id`와 표시 문구 `label`의 JSON 배열로 저장한다. 선택 답변은 서버가 해당 질문의 선택지 ID를 검증한 뒤 저장된 `label`을 사용자 메시지의 `content`에 저장한다. 직접 입력도 같은 텍스트 메시지로 저장한다. `002_message_submission.sql`은 최초 POST의 선택지 ID를 `selected_option_id`, 직접 입력을 `submitted_content`에 보존한다. 선택 답변은 전자만, 직접 입력은 후자만 채운다. PUT은 두 컬럼을 바꾸지 않는다. 기존 행은 둘 다 NULL로 유지하고 재전송 시 충돌 처리한다. `sender`는 `user` 또는 `assistant`다. 사용자 메시지에는 `client_message_id`가 필수다. 질문 내용은 `questions`, AI의 짧은 대화 응답은 `messages`에 저장하고 대화 순서에 따라 화면에 조합한다. 순서는 기록별로 관리하며 질문 생성과 AI 응답 저장을 함께 처리한다.

## 제약과 인덱스

- `messages(record_id, client_message_id)`는 유일하다. 같은 요청의 재전송은 기존 메시지를 반환한다.
- 질문과 메시지의 순서는 기록 안에서 중복되지 않게 관리한다. `questions(record_id, sequence)`와 `messages(record_id, sequence)`에 각각 유일 제약을 둔다. 두 테이블 사이의 대화 순서는 같은 기록의 트랜잭션에서 조정한다.
- 업체와 지역, 업체와 작업 연결은 각각 두 ID를 복합 기본키로 사용한다. 검색을 위해 지역 ID와 작업 ID를 앞에 둔 역방향 인덱스도 둔다.
- `records(owner_id)`에 인덱스를 둔다. 질문·메시지의 기록별 순서 조회에는 위 유일 인덱스를 사용한다.
- 메시지에 연결된 질문은 같은 하자 기록에 속해야 한다. 서버 검증과 복합 외래키로 보장한다.

## 갱신 규칙

입력 변경 시 기록 행을 잠근 트랜잭션에서 현재 입력 버전을 확인하고, 변경과 버전 증가를 함께 처리한다. 사용자 메시지 수정은 이후 대화와 질문 삭제도 같은 트랜잭션에서 처리한다. 생성 결과 저장 시 생성에 사용한 버전과 현재 버전을 비교한다.

진단의 최신 여부는 생성에 사용한 입력 버전으로 판단한다. 진단 저장 성공 시 `diagnosis_generation`을 증가시킨다. 요청문은 생성에 사용한 입력 버전과 진단 생성 번호가 모두 현재 값과 일치해야 최신이다. 요청문 저장 직전에도 두 값을 트랜잭션에서 검사한다. 진단 재생성 실패 시 생성 번호와 기존 결과를 유지한다. 현재 버전 결과는 재사용하며, 명시적인 재생성만 모델을 다시 호출한다. 실패한 생성으로 기존 값을 덮어쓰지 않는다.

다음 질문 API의 성공 응답 전체를 `next_question_result`에, 사용한 입력 버전을 `next_question_revision`에 저장한다. 응답에는 `source="sample"`과 질문·선택지·짧은 AI 응답이 포함된다. 질문과 짧은 응답이 모두 null인 종료 응답도 저장한다. 질문·메시지 행과 완료 응답은 같은 입력 버전 검사와 트랜잭션에서 저장한다. 현재 버전과 저장 버전이 같으면 그대로 재사용한다. 호출 실패는 완료 응답으로 저장하지 않는다.

다음 질문을 저장할 때 새 질문과 AI 응답에는 생성에 사용한 현재 `input_revision`을 기록하지만 기록의 입력 버전은 올리지 않는다. 인식한 답변의 질문은 `answered=true`로 닫고, 관련 없는 메시지는 `answered`를 바꾸지 않는다. `unknown` 답변은 질문을 닫는 데만 사용하고 확인된 사실로 저장하지 않는다. 과거 메시지를 수정하면 그 답변의 질문을 `answered=false`로 되돌리고 `next_question_result`·`next_question_revision`을 NULL로 지워, 삭제된 질문을 담은 이전 응답을 조회하거나 재사용하지 않게 한다. 시연용 다음 질문은 기존 컬럼만 사용하며 스키마 변경 마이그레이션은 없다. `005_next_question_grants.sql`은 런타임 역할의 questions INSERT/UPDATE 권한만 추가한다.

샘플 업체는 실제 업체 테이블에 섞어 넣지 않고 검색 API가 빈 결과일 때 반환한다. 수정한 요청문은 앱의 현재 화면에서만 유지한다.

## 구현 전 확인

- 지원 하자 유형, 검색 지역, 작업 목록 및 원인 점검 항목
- 개인정보 보관 범위와 보유기간, 외부 DB 서비스에 적용되는 대회 규정의 범위
- 이미지 담당자와 YOLO 임시 응답 계약 및 실행 환경
