# 개발 환경·DB·테스트 가이드

프로젝트 개요와 빠른 시작은 [README](../../README.md), API 동작·호출 예시 및 구현 메모는 [API 사용 가이드](API_USAGE.md)를 확인합니다.

## 상세 디렉토리 구조와 의존성 관리

```text
package.json       npm workspaces와 공통 실행 스크립트
apps/
  api/
    pyproject.toml uv 프로젝트와 의존성
    uv.lock        잠금 파일
    .python-version Python 3.13
    app/
      main.py      FastAPI 앱, 오류 응답
      errors.py    공통 오류 응답 헬퍼
      auth.py      Supabase JWT 검증
      records.py   기록·메시지·다음 질문·일괄 분석 API
      profile.py   내 프로필·지역 목록 API
      support_programs.py 소식지 목록·상세 API
      support_sync.py 보조금24 수동 동기화
      drafts.py    임대인·업체 요청문 생성 및 기본 양식 API
      diagnosis.py 사진 관찰·입력 기반 구조화 진단 생성·재생성 API
      llm.py       OpenAI 호환 Chat Completions 호출 클라이언트(텍스트·JSON·이미지)
      providers.py 작업 종류·업체 검색 API
      chat.py      요청인–업체 1:1 채팅 REST API
      sample_questions.py 시연용 질문 규칙과 결정 함수
      sample_analysis.py 샘플 일괄 분석 결정 함수
      schemas.py   요청·응답 모델
      db.py        요청별 DB 트랜잭션
      migrate.py   SQL 마이그레이션 실행기
      vision.py    YOLO 탐지·동의 기반 Meta SAM 3.1 분할·비전 LLM 보조 관찰
      config.py    환경변수
    migrations/    순서대로 적용하는 SQL 마이그레이션
    tests/         실제 PostgreSQL 통합 테스트
    .env.example
  mobile/
    app.json       Expo 설정
    src/app/       Expo Router 로그인·프로필·분석 입력·결과 화면
    src/lib/       Supabase·FastAPI 클라이언트
    .env.example
docs/
  COMMIT_CONVENTION.md 커밋 메시지 규칙
  guides/
    DEVELOPMENT.md 개발 환경·DB·테스트 가이드
    API_USAGE.md   API 동작·호출 가이드 및 구현 메모
  plans/           MVP·프로젝트 계획
  design/          백엔드·DB·API 설계
  ideas/           AI 기능 후보 비교
```

Python 의존성은 `apps/api/pyproject.toml`과 `uv.lock`이, JavaScript 의존성은 루트 `package.json`과 `package-lock.json`이 관리합니다. 명령은 저장소 루트에서 실행합니다. npm workspace에는 `apps/mobile`만 등록되어 있고, `apps/api`는 uv 프로젝트로 따로 동작합니다.

`uv`가 `apps/api/.python-version`(3.13)의 Python과 `apps/api/.venv`를 관리합니다. 잠금 파일 기준으로 정확히 설치하려면 `uv sync --locked --directory apps/api --extra vision`를 사용합니다.

- Python 의존성 추가: `uv add --directory apps/api <package>`
- Python 개발 의존성 추가: `uv add --dev --directory apps/api <package>`
- Python 잠금 갱신: `uv lock --directory apps/api`
- JavaScript 의존성 추가: `npm install <package> --workspace @career-pair/mobile`
- Expo 패키지 추가: `cd apps/mobile && npx expo install <package>`

`apps/api/.venv/`, `node_modules/`, `.env`는 생성물이므로 커밋하지 않습니다.

## 실행 상세

```bash
npm run api       # FastAPI, 0.0.0.0:8000
npm run mobile    # Expo 개발 서버
```

- 상태 확인: `GET http://127.0.0.1:8000/health`
- API 문서: `http://127.0.0.1:8000/docs` (Scalar)

### Scalar에서 로그인하고 API 실행하기

`apps/api/.env`에 `SUPABASE_PUBLISHABLE_KEY`를 설정합니다. 모바일의 `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`와 같은 공개 키를 사용하며, service role 키는 사용하지 않습니다. 환경변수 변경 후 API 서버를 재시작합니다.

1. `/docs`의 Authentication에서 `SupabaseLogin`을 선택합니다.
2. Password 흐름의 Username에 Supabase 계정 이메일, Password에 비밀번호를 입력합니다. Client ID와 Client Secret은 비워 둡니다.
3. 토큰 발급 버튼을 누르면 `/auth/token`이 Supabase 로그인을 중계하고 Scalar가 받은 토큰을 인증이 필요한 요청에 적용합니다.
4. 원하는 API의 Test Request에서 경로·본문을 채우고 Send를 누릅니다. 토큰이 만료되면 다시 로그인합니다.

기존 `HTTPBearer` 토큰 직접 입력도 사용할 수 있습니다. 로그인은 이메일·비밀번호 계정용이며, MFA 추가 인증과 토큰 자동 갱신은 지원하지 않습니다. 비밀번호는 API를 거쳐 Supabase로 전달되므로 로컬에서는 localhost를, 외부 배포에서는 HTTPS를 사용합니다. 토큰 응답은 캐시하지 않으며 Scalar 인증값의 영구 저장도 활성화하지 않습니다.

`npm run api`는 실제 기기에서 접근할 수 있도록 `0.0.0.0`에 바인딩합니다. 신뢰하는 네트워크에서만 실행하고, 인증은 그대로 필요합니다. 서버는 요청 본문, 비밀번호, 액세스 토큰을 로그에 남기지 않습니다. 기본 uvicorn 액세스 로그에는 메서드와 경로만 남습니다.

모바일 앱은 Expo Go 또는 시뮬레이터에서 실행합니다. `apps/mobile/.env`의 `EXPO_PUBLIC_API_URL`은 실행 대상에 맞춰야 합니다.

| 실행 대상 | `EXPO_PUBLIC_API_URL` |
| --- | --- |
| iOS Simulator | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기 + Expo Go | `http://<Mac LAN IP>:8000` |

실제 기기는 Mac과 같은 Wi-Fi에 연결해야 합니다. Supabase 설정은 API의 `apps/api/.env`와 앱의 `apps/mobile/.env`가 같은 프로젝트를 가리켜야 하며, 앱에는 publishable/anon key만 넣고 service role 키는 넣지 않습니다.

## 환경변수

### 백엔드 환경변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 예 | FastAPI 런타임 연결. `career_pair_runtime`처럼 DML 권한만 가진 계정 |
| `MIGRATION_DATABASE_URL` | 마이그레이션 시 | 테이블·역할·권한을 만드는 관리자 연결 |
| `SUPABASE_URL` | 예 | `https://<project-ref>.supabase.co`. 발급자는 여기에 `/auth/v1`을 붙인 값 |
| `SUPABASE_JWT_SECRET` | HS256 토큰만 | 기존 Supabase JWT secret. 비대칭 서명 키를 쓰면 비워 둔다 |
| `SUPABASE_JWT_AUDIENCE` | 아니오 | 기본 `authenticated` |
| `SUPABASE_JWT_ISSUER` | 아니오 | 기본 `SUPABASE_URL + /auth/v1`. 로컬 Supabase 등에서 재정의 |
| `GOV24_API_KEY` | 아니오 | 소식지(공공데이터포털 보조금24 Open API) 수동 동기화용 인증키. 미설정 시 검증 시드로 조회하며 동기화 명령은 건너뜁니다. 서버 환경변수로만 사용 |
| `LLM_API_KEY` | 사진·진단·요청문 모델 사용 시 | 서버 전용 모델 API 키. 미설정 시 진단은 `503`(`llm_unavailable`)이고 요청문 기본 양식 API는 계속 동작합니다. `YOLO_MODEL_PATH`만 설정하고 이 키가 없으면 일괄 분석도 `503`입니다 |
| `LLM_BASE_URL` | 아니오 | 기본 `https://api.openai.com/v1`. OpenAI 호환 Chat Completions 서버 주소 |
| `LLM_MODEL` | 아니오 | 기본 `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | 아니오 | 기본 20초. 초과하면 `504`(`llm_timeout`)입니다 |
| `VISION_LLM_MODEL` | 아니오 | YOLO가 읽지 못한 사진을 관찰할 비전 모델. 비어 있으면 `LLM_MODEL`을 사용합니다 |
| `YOLO_MODEL_PATH` | 아니오 | 서버 로컬 YOLO 탐지 체크포인트 경로. `LLM_API_KEY`와 함께 설정해야 하며, 둘 다 없으면 샘플 모드입니다 |
| `MODEL_API_KEY` | 아니오 | Meta SAM 3.1 API 키. 외부 분석 동의가 있을 때만 사용합니다 |
| `SAM_TIMEOUT_SECONDS` | 아니오 | 기본 30초. SAM 실패 시 YOLO 탐지 결과는 유지합니다 |
| `SUPABASE_STORAGE_BUCKET` | 아니오 | 하자 사진 비공개 버킷 이름. 기본 `defect-photos` |
| `SUPABASE_STORAGE_KEY` | Storage 사용 시 | 서버 전용 Storage 키. 없으면 `SUPABASE_SERVICE_ROLE_KEY`, 둘 다 없으면 업로드·서명을 생략합니다 |
| `STORAGE_SIGNED_URL_TTL_SECONDS` | 아니오 | Signed URL 만료 시간(초). 기본 300 |

`apps/api/.env`는 커밋하지 않습니다.

### Supabase Storage 비공개 버킷

Supabase 대시보드 **Storage → New bucket**에서 이름 `defect-photos`, **Public bucket 해제**로 만들거나 아래 SQL을 실행합니다.

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('defect-photos', 'defect-photos', false)
ON CONFLICT (id) DO NOTHING;
```

서버에 `SUPABASE_STORAGE_KEY`(또는 `SUPABASE_SERVICE_ROLE_KEY`)를 설정하면 분석 시 긴 변 1600px·EXIF 제거 JPEG가 `{owner}/{record}/{role}_{uuid}.jpg`로 업로드되고, 조회 시 5분 Signed URL이 발급됩니다. 키가 없으면 업로드를 건너뛰고 `photos=[]`로 동작합니다. 서비스 키는 절대 모바일 번들·로그·문서에 기록하지 않습니다.

### 업체 계정·시연 데이터 준비

샘플 업체는 API가 빈 검색 결과에서만 반환하는 고정 시연 후보이며 `providers` 테이블에 넣지 않습니다. 실제 업체를 검색·채팅에 쓰려면 팀이 확인한 업체명·전화번호·평점·소개와 Supabase Auth 업체 계정 UUID를 **관리자 SQL**로 연결합니다. `014_yongin_provider_seed.sql`은 공식 출처 확인 후 채우는 템플릿이며, 팀 확인 자료가 없어 실제 행은 넣지 않았습니다. 공개 관리 API는 없고 일반 가입자는 업체로 승격되거나 `account_user_id`를 연결할 수 없으며, 런타임 역할에는 `providers` `SELECT` 권한만 있습니다.

```sql
INSERT INTO providers
    (name, phone, rating, review_count, description, address,
     business_hours, career_years, account_user_id)
VALUES
    ('<확인된 업체명>', '<확인된 전화번호>', 0.0, 0,
     '<확인된 소개>', '<확인된 주소>', '<확인된 영업시간>', NULL,
     '<provider auth user id>')
RETURNING id;

INSERT INTO provider_regions (provider_id, region_id)
SELECT '<provider id>', id FROM regions WHERE name = 'yongin';

INSERT INTO provider_work_types (provider_id, work_type_id)
SELECT '<provider id>', id FROM work_types WHERE name = '곰팡이 제거';
```

`010` 마이그레이션이 작업 종류 4건(`곰팡이 제거`, `균열 보수`, `벽지·도장 보수`, `원인 점검`)을 시드하고, `013`이 업체 평점·소개·주소·영업시간·경력 컬럼과 `providers_rating_idx`를 추가합니다. 실제 업체·연락처·출장 지역 데이터는 팀 확인 자료가 없어 등록하지 않았습니다. `GET /providers`는 `region_id` 필수·`work_type_id` 선택이며 별점 내림차순으로 반환하고, `GET /providers/{provider_id}`로 상세를 조회합니다. 실제 후보가 없으면 `GET /providers`는 `is_sample=true` 샘플을 반환하며, 앱 내 채팅은 `account_user_id`가 연결된 업체만 가능합니다(`chat_available=true`, 샘플·계정 미연결 업체로는 채팅방을 만들 수 없음). 비밀번호·토큰은 문서에 기록하지 않습니다.

### 모바일 환경변수

`apps/mobile/.env`에 설정합니다. `EXPO_PUBLIC_` 값은 앱 번들에 포함되므로 공개 값만 넣습니다.

| 변수 | 설명 |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | FastAPI 주소. 실제 기기에서는 Mac의 LAN IP |
| `EXPO_PUBLIC_SUPABASE_URL` | API의 `SUPABASE_URL`과 같은 Supabase 프로젝트 URL |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key 또는 기존 anon key. service role 키는 금지 |

## 로컬 PostgreSQL 설정

```bash
createdb career_pair

MIGRATION_DATABASE_URL=postgresql://localhost:5432/career_pair \
  uv run --directory apps/api python -m app.migrate

# 마이그레이션이 만든 런타임 역할에 로그인 비밀번호를 지정한다.
psql postgresql://localhost:5432/career_pair \
  -c "ALTER ROLE career_pair_runtime LOGIN PASSWORD 'change-me'"
```

`apps/api/.env`의 `DATABASE_URL`을 `postgresql://career_pair_runtime:change-me@localhost:5432/career_pair`로 맞춥니다.

마이그레이션은 `schema_migrations`에 적용 이력을 남기므로 다시 실행해도 완료된 파일은 건너뜁니다. 관리자 연결은 테이블과 역할을 만들고, 런타임 연결은 이번 API에 필요한 권한만 가집니다: 기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/INSERT/UPDATE/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 프로필 `SELECT/INSERT/UPDATE`, 지원 사업 `SELECT/INSERT/UPDATE`, 채팅방·채팅 메시지 `SELECT/INSERT/UPDATE`, 업체·지역·작업 참조 테이블 `SELECT`. 질문 INSERT/UPDATE 권한은 `005_next_question_grants.sql`, 프로필 권한은 `007_profiles_and_regions.sql`, 지원 사업 권한은 `008_support_programs.sql`, 채팅방·채팅 메시지(`chat_rooms`·`chat_messages`) 권한은 `010_chat_and_provider_accounts.sql`에서 추가합니다(`providers`는 `SELECT`만 유지). 지원 사업 DELETE 권한은 없습니다. 런타임 역할은 `auth.users`를 읽거나 DDL을 실행할 수 없습니다. 새 기능이 더 많은 권한을 필요로 하면 새 마이그레이션에서 명시적으로 부여합니다.

## Supabase 사용 시

1. Supabase의 **direct connection**(풀러가 아닌 5432 포트) 관리자 자격증명으로 마이그레이션을 실행합니다.
   ```bash
   MIGRATION_DATABASE_URL='postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres' \
     uv run --directory apps/api python -m app.migrate
   ```
   Supabase에는 이미 `auth.users`가 있으므로 `auth` 스키마에 DDL을 실행하지 않고, `records.owner_id` 외래키만 추가됩니다.
2. 런타임 역할의 비밀번호를 설정하고 `DATABASE_URL`에 Supabase 연결 문자열(`sslmode=require` 권장)을 넣습니다.
   ```sql
   ALTER ROLE career_pair_runtime LOGIN PASSWORD '<runtime-password>';
   ```
3. `SUPABASE_URL`과 JWT 설정을 채웁니다. 새 프로젝트가 비대칭 서명 키(`RS256`/`ES256`)를 쓰면 `SUPABASE_JWT_SECRET` 없이 JWKS(`/auth/v1/.well-known/jwks.json`)로 검증합니다. 기존 HS256 토큰이면 secret을 설정합니다.
4. 앱 테이블은 마이그레이션에서 Supabase Data API 역할(`anon`, `authenticated`, `service_role`)의 권한을 회수합니다. Supabase 대시보드의 Data API 노출 스키마에 별도 권한을 추가하지 마세요. 앱은 테이블을 직접 노출하지 않고 FastAPI를 통해서만 접근합니다.
5. `003_backend_rls.sql`은 앱 테이블의 RLS를 켜고 전용 `career_pair_runtime` 역할만 통과시킵니다. 사용자별 소유권 검사는 FastAPI가 담당하므로 이 DB 계정은 서버에서만 사용합니다. `schema_migrations`는 관리자만 접근합니다. `004_protect_rls_trigger.sql`은 Supabase 내부 RLS 이벤트 트리거가 있을 때 공개 실행 권한을 회수합니다. `005_next_question_grants.sql`은 다음 질문 API가 질문을 생성·갱신할 수 있도록 런타임 역할에 `questions` INSERT/UPDATE를 부여합니다. `006_records_material.sql`은 `records.material` 컬럼을 추가합니다. `007_profiles_and_regions.sql`은 `profiles`·RLS·런타임 권한과 내 기록 목록용 인덱스를 만들고 시연 지역 용인을 시드합니다. `008_support_programs.sql`은 지역 상하 관계와 `support_programs`·RLS·런타임 권한을 추가하고, `009_support_program_seed.sql`은 공식 원문으로 확인한 주거 지원 공고 4건을 중복 없이 시드합니다. `010_chat_and_provider_accounts.sql`은 `providers.account_user_id`, 작업 종류 시드, `chat_rooms`·`chat_messages`·RLS·런타임 권한을 추가합니다.

IPv4 네트워크에서는 대시보드 **Connect → Session pooler**의 호스트와 5432 포트를 사용합니다. 전용 역할의 풀러 사용자 이름은 `career_pair_runtime.<project-ref>`이며 `sslmode=require`를 붙입니다. 호스트의 `aws-0`/`aws-1` 부분은 프로젝트 연결 정보에 맞춰야 합니다. [공식 연결 문서](https://supabase.com/docs/guides/database/connecting-to-postgres)를 참고하세요.

현재 개발 환경은 **Home Keeper** (`lprqztpobrlhetbjkcks`, Sydney)에 연결되어 있습니다. 2026-11-20에 Supabase 플러그인으로 006–010을 적용했으며, 마이그레이션 001–010이 모두 적용된 상태입니다. `011_chat_read_state.sql`–`015_quote_requests_and_proposals.sql`은 로컬 테스트 DB에서 검증했으며 Home Keeper에는 아직 적용하지 않았습니다. `records.material`, 프로필·지원 사업·채팅 테이블과 런타임 계정의 조회, 새 테이블 4개의 RLS 정책을 실제 DB에서 확인했습니다. 지원 사업 4건과 작업 종류 4건의 시드도 확인했습니다. 인증은 ES256/JWKS를 사용하므로 `SUPABASE_JWT_SECRET`은 비워 둡니다. API와 모바일의 Supabase URL을 맞췄으며, 모바일 publishable key로 Auth health·settings 응답 200을 확인했습니다. 모바일 API 주소는 우선 `http://127.0.0.1:8000`으로 설정했습니다. 실제 기기에서는 Mac LAN IP로 변경해야 합니다. 실제 Supabase에 테스트 스위트의 `TEST_ADMIN_DATABASE_URL`을 지정하지 마세요.

## 테스트

```bash
npm run api:test
```

테스트는 실제 PostgreSQL을 사용합니다. 기본값은 `postgresql://localhost:5432/postgres`에 현재 OS 사용자로 접속해 `career_pair_test` 데이터베이스를 **삭제 후 재생성**하고, 빈 DB에 마이그레이션을 적용한 뒤 런타임 역할로 API를 호출합니다. 다음 권한이 필요합니다.

- `CREATE DATABASE`, `DROP DATABASE`
- `CREATE ROLE`(마이그레이션이 런타임 역할 생성), 역할 비밀번호 변경(`ALTER ROLE`)

다른 서버를 쓰려면:

```bash
TEST_ADMIN_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres \
TEST_DATABASE_NAME=career_pair_ci_test \
  npm run api:test
```

`TEST_DATABASE_NAME`은 `_test`로 끝나야 하며, 운영 DB를 가리키는 이름은 거부합니다. 테스트는 클러스터의 `career_pair_runtime` 역할 비밀번호를 테스트 값으로 변경하므로 로컬 개발 클러스터에서만 실행하세요. 테스트는 실제 Supabase에 연결하지 않고 로컬에서 서명한 HS256 토큰을 사용합니다. 인증 경계는 FastAPI의 `app.dependency_overrides`로 대체할 수 있지만, 운영 코드에는 인증 우회 경로가 없습니다.

검증 항목: 빈 DB 마이그레이션, 서명·만료·발급자·대상 검증, 소유권 격리, 다른 기록 질문 거부, 선택지/직접 입력 저장, 메시지 재전송 멱등성, 동일 ID 내용 충돌, 오래된 버전 거부, 과거 메시지 수정 시 후속 대화 삭제, 동일 내용 수정 무변경, 동시 요청 중복·순서 방지, 수정 실패 시 롤백, DB 제약과 런타임 권한. 다음 질문은 첫 질문·선택지, 선택/직접 입력 진행, 관련 없는 메시지 미확정, 모름 답변 종료, 같은 버전 재사용, 종료 응답 재사용, 동시 생성 중복 방지, 생성 중 입력 변경 409, 생성 실패 무저장, 과거 답변 수정 후 오래된 질문·캐시 미재사용을 검증합니다.

일괄 분석은 사진 1·2장 정상 저장/재조회, `material`·분석 지역 스냅샷 저장, 다른 사용자 접근 404, 사진 없음·3장·잘못된 형식·10MB 초과·역할 불일치 422, 같은 입력 재분석 시 버전 유지, 분석 중 입력 변경 409, 동시 분석의 입력/진단 혼합 방지, 샘플 결과에 bbox·confidence가 없음을 검증합니다. 사진 관찰은 라벨 한국어 정규화(`raw_label` 보존), bbox·SAM 마스크 기반 `area_ratio`, YOLO 미탐지·실행 불가 시 사진별 비전 LLM 보조 관찰, 판독 불가·호출 실패의 사진별 `failed` 기록, YOLO와 비전 LLM이 섞인 응답의 `yolo_vision_llm` 표시, `YOLO_MODEL_PATH`만 있고 `LLM_API_KEY`가 없을 때 `503`을 검증합니다. 진단은 심각도 구간 강제 정규화, 증거 없음·`null` 심각도의 판단 보류 전환, 의심 유형 용어 정규화, 등록 작업 종류 매칭·`원인 점검` 폴백, 프롬프트의 좌표·RLE·SVG 제외와 연락처 마스킹, 입력 버전 일치 시 모델 미호출 재사용, 재생성 저장, 모델 실패 시 기존 진단 보존, 생성 중 입력 변경 409를 검증합니다. 업체는 인증, 필수 지역·선택 특화 분야 검증, 별점·리뷰·이름 정렬, `specialty_work_types` 반환, 빈 결과에서만 샘플 폴백, 상세의 평점·지역·특화 분야, 없는 업체·샘플 UUID 404, 평점 CHECK 제약, 용인 시드 템플릿 멱등성을 검증합니다. Storage는 EXIF 회전·리사이즈·EXIF 제거 업로드, 단기 Signed URL, DB 충돌 시 업로드 롤백 삭제, 키 미설정 생략, 소유자 외 접근 404를 검증합니다. 견적 요청서는 진단·중복 공개·업체 생성 거부·지역·작업 검증, 역할별 목록·상세 격리, 업체 경쟁 제안 비노출, 제안 중복·가격 범위·마감, 1건 수락과 나머지 마감, 동시 수락 [200, 409], 수락 전후 채팅방 생성, 취소 시 제안 마감을 검증합니다. 프로필·지역·내 기록 목록은 사용자별 프로필 격리, 최초 등록·수정·upsert 재시도, 역할 변경 거부·업체 역할 보존, 닉네임·지역·거주 형태 검증, 용인 지역 시드, 본인 기록만 최근 수정순 요약 반환, 진단 없는 기록의 `null`/빈 배열 처리를 검증합니다. 업체 계정의 `provider_id` 반환과 `role='provider'` 보존, 일반 요청인의 `provider_id=null`도 검증합니다. 지역은 분석 시 프로필 기본값·명시 지역·기존 값 유지, 실제 변경 시 버전 증가, 잘못된 지역 422, PATCH 설정·해제·검증, `region_name` 조인을 검증합니다. 소식지는 프로필 지역·상위 지역·전국 포함, `limit`/`offset` 페이지와 `total`·`has_more`, 빈 초과 페이지의 정확한 total, `status=active` 필터의 total 일치, 다른 지역 제외, 거주 형태 정렬, 한국 시간 마감 경계, 상시·기한 불명 구분, 상세·빈 목록·프로필 미등록·없는 공고, URL CHECK, 시드 반복, 동기화 upsert, API 키 미설정, 페이지 중간 실패·잘못된 응답 시 기존 데이터 보존을 검증합니다. 요청문·업체 검색·채팅은 소유권, 재사용·재생성, 입력·진단 버전 충돌, 모델 실패 시 기존 값 보존·기본 양식, 키 미설정, 프롬프트 개인정보 제외, 지역·작업 동시 일치·샘플 폴백·DB 오류 구분, 방 재사용·동시 생성·요약 중복 방지, 참여자 권한·비참여자 404, 업체의 원본 기록 차단, 메시지 멱등성·내용 충돌·정렬·페이지를 검증합니다. LLM 테스트는 고정 응답으로 대체합니다. 백엔드 전체 테스트 160개가 통과했습니다.

채팅은 방 생성·재사용, 요약 중복 방지, 비참여자 404, 메시지 멱등성·정렬·페이지, WebSocket 누락·잘못된 토큰 `4401`, 참여자 양쪽 수신, 요약 수신, 재연결, 멱등 재전송 이벤트 중복 없음, 방별 미읽음 수와 본인 메시지 제외, 읽음 처리 후 재집계를 검증합니다. WebSocket 테스트는 `TestClient`로 실제 앱의 소켓 핸들러를 호출하며, 연결 레지스트리는 테스트마다 별도 허브로 검증합니다.

모바일 타입 검사:

```bash
npm run typecheck --workspace @career-pair/mobile
```

Expo Router 타입 생성 후 통과했습니다. 모바일은 `profile.role`에 따라 요청인 홈(분석 시작·업체 찾기·내 정보)과 업체 홈(업체 상세·평점·특화 분야·받은 견적 요청서)을 분기합니다. 요청인은 결과에서 사진·견적 요청서 작성·도착 제안서 비교·수락·취소·채팅을, 업체는 요청서 상세에서 제안서 제출과 내 제안 상태를 사용합니다. 실제 기기/시뮬레이터에서 Supabase 로그인 후 프로필 저장·사진 선택·제출·결과 표시·업체 목록·상세·기록 재열람 흐름은 이번 환경에서 실행하지 못했습니다. Home Keeper의 스키마와 런타임 조회·Auth 서버 연결은 확인했지만, 실제 사용자 토큰으로 분석·프로필·목록·소식지·업체 검색·채팅 API를 호출하는 흐름은 검증하지 못했습니다.

## 단계별 구현 상태

- 1단계: 사진 관찰·텍스트 진단 — 구현 완료
- 2단계: 분석 지역 스냅샷·소식지 페이지네이션 — 구현 완료
- 3단계: 업체 상세·평점·별점순 추천·Role 분기 — 구현 완료
- 4단계: 비공개 Storage 사진·견적 요청서·제안서·1건 수락 — 구현 완료
- 남은 운영 항목: Home Keeper DB에 `011`–`015` 적용, Storage 비공개 버킷·서버 키 설정, 소식지 보조금24 주기 동기화

## 소식지 시드·보조금24 동기화

`008_support_programs.sql`과 `009_support_program_seed.sql`이 적용되면 전국·경기도·용인시의 검증 공고 4건이 `source='seed'`로 들어갑니다. 시드는 고정 `external_id`와 `ON CONFLICT DO NOTHING`을 사용하므로 `009`를 다시 실행해도 중복되지 않습니다.

보조금24 Open API 동기화는 수동 명령 하나로 실행합니다. 서버 환경변수의 `DATABASE_URL`과 `GOV24_API_KEY`만 사용하며, API 키는 코드·DB·로그에 저장하지 않습니다.

```bash
set -a
. apps/api/.env
set +a

npm run api:sync-support-programs
```

또는:

```bash
GOV24_API_KEY='<data.go.kr serviceKey>' \
DATABASE_URL='postgresql://career_pair_runtime:...@localhost:5432/career_pair' \
  uv run --directory apps/api python -m app.support_sync
```

- `GOV24_API_KEY`가 없으면 동기화만 건너뛰고 기존 시드/DB는 그대로 유지합니다. 목록·상세 API는 외부 API를 호출하지 않으므로 계속 동작합니다.
- 공식 데이터: [행정안전부_대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do), `GET https://api.odcloud.kr/api/gov24/v3/serviceList`. 공식 문서 기준 `page`·`perPage`·`returnType`·`serviceKey`와 서비스ID·서비스명·소관기관·지원대상·지원내용·신청기한·상세조회URL 등의 필드를 사용합니다.
- 이용 조건: 공식 페이지의 이용허락범위는 **제한 없음**으로 확인했습니다. 동기화 행의 `source_attribution`은 `행정안전부 대한민국 공공서비스(혜택) 정보 · 공공데이터포털`입니다.
- 동기화는 모든 페이지를 먼저 수집하고 전체 건수를 검증한 뒤 한 트랜잭션에서 주거 관련 행만 upsert합니다. 타임아웃·인증 오류·잘못된 응답·페이지 중간 실패 시 기존 행과 시드를 삭제하거나 덮어쓰지 않습니다. 삭제 권한·삭제 API는 없습니다.
- 지역은 `소관기관명`이 등록 지역 표시명과 정확히 일치할 때만, 거주 형태는 원문에 명시된 경우만 태그합니다. 모호한 지역·자격·마감은 추론하지 않고 `unknown`으로 남기거나 저장하지 않습니다. 서비스명에 주거 관련 키워드가 있는 사업만 동기화합니다.
- 검증 시드와 같은 제목(끝의 `사업` 제외)·기관·지역의 API 행은 목록에서 시드로 대체해 같은 공고가 두 번 보이지 않게 합니다.
- 시드 출처와 확인 시점(2026-11-20):
  - [복지로 청년월세 지원사업](https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004661)
  - [경기청년포털 자립준비청년 주거비 지원사업](https://youth.gg.go.kr/gg/intro/youth-policy-educational-testing.do?articleNo=9010&mode=view)
  - [용인청년포털 부동산 중개보수 감면](https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026021000000000000055001)
  - [용인청년포털 청년월세 지원](https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026032300000000000061001)
- 실제 `GOV24_API_KEY`로 `serviceList` **10,891건**을 조회하고, 주거 제목 필터·지역 확정 후 **41건을 로컬 개발 DB에 upsert**하는 것까지 확인했습니다. Home Keeper에도 `support_programs` 마이그레이션과 시드 4건을 적용했으며, 실제 Supabase 대상 보조금24 동기화는 아직 실행하지 않았습니다. 운영 응답의 주거 키워드·지역·기한 해석은 첫 실동기화 결과를 계속 점검해야 합니다.
