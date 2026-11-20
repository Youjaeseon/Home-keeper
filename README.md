# Career Pair (MVP)

하자 기록을 저장하는 FastAPI + PostgreSQL 백엔드와 Expo 모바일 앱을 한 저장소에서 관리합니다. 인증은 Supabase Auth(이메일·비밀번호) 액세스 토큰을 사용합니다.

현재 백엔드 코드에는 `POST /records`, `GET /records`, `GET /records/{record_id}`, `PATCH /records/{record_id}`, `POST /records/{record_id}/analyze`, `POST /records/{record_id}/messages`, `PUT /records/{record_id}/messages/{message_id}`, `POST /records/{record_id}/next-question`, `GET /me/profile`, `PUT /me/profile`, `GET /regions`, `GET /support-programs`, `GET /support-programs/{program_id}` 열세 개 API가 구현되어 있습니다. 모바일 앱은 로그인, 프로필 등록·수정, 사진·위치·재질 입력, 샘플 분석 제출, 결과 화면과 내 분석 기록 목록까지 구현했습니다. `messages`·`next-question`은 현재 MVP 흐름에서 미사용/보류 레거시 상태입니다.

2026년 11월 20일 팀 회의 변경에 따라 MVP 목표 설계를 아래 내용으로 갱신했습니다. 사진·위치·재질 일괄 분석은 실제 모델 없이 **샘플 결과**로 먼저 구현했고, 프로필·내 기록 목록은 API와 모바일 화면을 구현했습니다. 주거 지원 사업 소식지는 백엔드 목록·상세·검증 시드·보조금24 수동 동기화를 구현했고, 모바일 소식지 화면은 후속입니다. 실제 모델·업체 검색·채팅은 후속 구현 예정입니다.
- **회원가입·프로필**: 닉네임, ID(이메일), PW, 거주 지역(필수), 등록 주소(선택), 거주 형태(`월세·전세·반전세·자가·기타`)
- **소식지 페이지**: 공공데이터포털 보조금24 Open API 동기화 + 검증된 시드 폴백으로 주거 지원 사업 제공, 마감 공고 흐림·하단 정렬
- **분석·결과 페이지**: 지원 하자 유형 `크랙·벗겨짐·곰팡이`, 시연 지역 `용인`. 분석 채팅창 없이 사진(1~2장)+위치+재질을 일괄 입력해 심각도(`0~100%` / `판단 보류`), `추정 원인`(AI 추정 안내·미확인 정보), `해결방안`, `재발 방지책` 표시(`자가`는 임대인 요청문 숨김)
- **업체 1:1 채팅·내 정보**: 하단 4개 탭(`소식지`·`분석`·`채팅`·`내 정보`), 요청인–업체 1:1 채팅(실시간 전송 방식은 팀원 협의 보류), `내 정보`의 프로필 수정·과거 기록 열람

## 문서 안내

팀 전체 흐름은 MVP 계획부터, 백엔드 구현과 앱 연동은 이 README와 API 설계부터 읽습니다.

| 문서 | 확인할 내용 |
| --- | --- |
| [백엔드 구현 체크리스트](docs/plans/BACKEND_CHECKLIST.md) | 구현된 기능, 남은 MVP 작업과 통합 검증 |
| [MVP 계획](docs/plans/MVP_PLAN.md) | 사용자 흐름, 역할, 시연 범위와 남은 제품 결정 |
| [백엔드 설계](docs/design/BACKEND_DESIGN.md) | 인증, 기록·일괄 분석·소식지·채팅 처리 규칙 |
| [DB 설계](docs/design/DB_DESIGN.md) | 테이블·제약·인덱스와 실제 마이그레이션에서 확정한 내용 |
| [API 설계](docs/design/API_DESIGN.md) | 현재 API 계약과 후속 API 계획, 요청·응답 예시 |
| [용어집](GLOSSARY.md) | 요청인, 업체, 거주 형태, 소식지, 주거 지원 사업, 하자 기록 등의 의미 |
| [프로젝트 계획](docs/plans/PROJECT_PLAN.md) | 제출 요건, 전체 일정, 검증표와 결정 이력 |
| [AI 아이디어 비교](docs/ideas/AI_IDEAS.md) | 후속 기능 후보와 검토 근거 |
| [커밋 규칙](docs/COMMIT_CONVENTION.md) | 커밋 메시지 형식, 타입·스코프 기준과 분리 원칙 |

현재 구현은 기록 API(위치·재질·증상), **사진·위치·재질 일괄 분석 샘플 API**, **회원 프로필·지역·내 기록 목록 API**, **주거 지원 사업 소식지 목록·상세·보조금24 수동 동기화**, DB(`001`–`009`), 모바일 로그인·프로필·분석 입력·결과·기록 목록 화면입니다. 설계 문서에 있는 소식지 모바일 화면, 실제 모델 기반 분석·진단, 요청문 생성, 업체 검색과 1:1 채팅, 회원가입 화면과 4개 탭은 후속 구현 대상입니다. 실행·환경 설정은 이 README를, 적용된 DB 구조는 [마이그레이션](apps/api/migrations/)을 함께 확인합니다.

## 구조

```text
package.json       npm workspaces와 공통 실행 스크립트
apps/
  api/
    pyproject.toml uv 프로젝트와 의존성
    uv.lock        잠금 파일
    .python-version Python 3.13
    app/
      main.py      FastAPI 앱, 오류 응답
      auth.py      Supabase JWT 검증
      records.py   기록·메시지·다음 질문·일괄 분석 API
      profile.py   내 프로필·지역 목록 API
      support_programs.py 소식지 목록·상세 API
      support_sync.py 보조금24 수동 동기화
      sample_questions.py 시연용 질문 규칙과 결정 함수
      sample_analysis.py 샘플 일괄 분석 결정 함수
      schemas.py   요청·응답 모델
      db.py        요청별 DB 트랜잭션
      migrate.py   SQL 마이그레이션 실행기
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
  plans/           MVP·프로젝트 계획
  design/          백엔드·DB·API 설계
  ideas/           AI 기능 후보 비교
```

Python 의존성은 `apps/api/pyproject.toml`과 `uv.lock`이, JavaScript 의존성은 루트 `package.json`과 `package-lock.json`이 관리합니다. 명령은 저장소 루트에서 실행합니다. npm workspace에는 `apps/mobile`만 등록되어 있고, `apps/api`는 uv 프로젝트로 따로 동작합니다.

## 준비

- Python 3.11 이상, [uv](https://docs.astral.sh/uv/)
- Node.js 20 이상, npm
- PostgreSQL 16 이상
- Supabase 프로젝트(인증용) 또는 로컬 테스트용 JWT

```bash
npm install
uv sync --directory apps/api
cp apps/api/.env.example apps/api/.env
cp apps/mobile/.env.example apps/mobile/.env
```

`uv`가 `apps/api/.python-version`(3.13)의 Python과 `apps/api/.venv`를 관리합니다. 잠금 파일 기준으로 정확히 설치하려면 `uv sync --locked --directory apps/api`를 사용합니다.

- Python 의존성 추가: `uv add --directory apps/api <package>`
- Python 개발 의존성 추가: `uv add --dev --directory apps/api <package>`
- Python 잠금 갱신: `uv lock --directory apps/api`
- JavaScript 의존성 추가: `npm install <package> --workspace @career-pair/mobile`
- Expo 패키지 추가: `cd apps/mobile && npx expo install <package>`

`apps/api/.venv/`, `node_modules/`, `.env`는 생성물이므로 커밋하지 않습니다.

## 실행

```bash
npm run api       # FastAPI, 0.0.0.0:8000
npm run mobile    # Expo 개발 서버
```

- 상태 확인: `GET http://127.0.0.1:8000/health`
- API 문서: `http://127.0.0.1:8000/docs` (Scalar)

`npm run api`는 실제 기기에서 접근할 수 있도록 `0.0.0.0`에 바인딩합니다. 신뢰하는 네트워크에서만 실행하고, 인증은 그대로 필요합니다. 서버는 요청 본문, 비밀번호, 액세스 토큰을 로그에 남기지 않습니다. 기본 uvicorn 액세스 로그에는 메서드와 경로만 남습니다.

모바일 앱은 Expo Go 또는 시뮬레이터에서 실행합니다. `apps/mobile/.env`의 `EXPO_PUBLIC_API_URL`은 실행 대상에 맞춰야 합니다.

| 실행 대상 | `EXPO_PUBLIC_API_URL` |
| --- | --- |
| iOS Simulator | `http://127.0.0.1:8000` |
| Android Emulator | `http://10.0.2.2:8000` |
| 실제 기기 + Expo Go | `http://<Mac LAN IP>:8000` |

실제 기기는 Mac과 같은 Wi-Fi에 연결해야 합니다. Supabase 설정은 API의 `apps/api/.env`와 앱의 `apps/mobile/.env`가 같은 프로젝트를 가리켜야 하며, 앱에는 publishable/anon key만 넣고 service role 키는 넣지 않습니다.

## 백엔드 환경변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 예 | FastAPI 런타임 연결. `career_pair_runtime`처럼 DML 권한만 가진 계정 |
| `MIGRATION_DATABASE_URL` | 마이그레이션 시 | 테이블·역할·권한을 만드는 관리자 연결 |
| `SUPABASE_URL` | 예 | `https://<project-ref>.supabase.co`. 발급자는 여기에 `/auth/v1`을 붙인 값 |
| `SUPABASE_JWT_SECRET` | HS256 토큰만 | 기존 Supabase JWT secret. 비대칭 서명 키를 쓰면 비워 둔다 |
| `SUPABASE_JWT_AUDIENCE` | 아니오 | 기본 `authenticated` |
| `SUPABASE_JWT_ISSUER` | 아니오 | 기본 `SUPABASE_URL + /auth/v1`. 로컬 Supabase 등에서 재정의 |
| `GOV24_API_KEY` | 아니오 | 소식지(공공데이터포털 보조금24 Open API) 수동 동기화용 인증키. 미설정 시 검증 시드로 조회하며 동기화 명령은 건너뜁니다. 서버 환경변수로만 사용 |

`apps/api/.env`는 커밋하지 않습니다.

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

마이그레이션은 `schema_migrations`에 적용 이력을 남기므로 다시 실행해도 완료된 파일은 건너뜁니다. 관리자 연결은 테이블과 역할을 만들고, 런타임 연결은 이번 API에 필요한 권한만 가집니다: 기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/INSERT/UPDATE/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 프로필 `SELECT/INSERT/UPDATE`, 지원 사업 `SELECT/INSERT/UPDATE`, 업체·지역·작업 참조 테이블 `SELECT`. 질문 INSERT/UPDATE 권한은 `005_next_question_grants.sql`, 프로필 권한은 `007_profiles_and_regions.sql`, 지원 사업 권한은 `008_support_programs.sql`에서 추가합니다. 지원 사업 DELETE 권한은 없습니다. 런타임 역할은 `auth.users`를 읽거나 DDL을 실행할 수 없습니다. 새 기능이 더 많은 권한을 필요로 하면 새 마이그레이션에서 명시적으로 부여합니다.

### Supabase 사용 시

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
5. `003_backend_rls.sql`은 앱 테이블의 RLS를 켜고 전용 `career_pair_runtime` 역할만 통과시킵니다. 사용자별 소유권 검사는 FastAPI가 담당하므로 이 DB 계정은 서버에서만 사용합니다. `schema_migrations`는 관리자만 접근합니다. `004_protect_rls_trigger.sql`은 Supabase 내부 RLS 이벤트 트리거가 있을 때 공개 실행 권한을 회수합니다. `005_next_question_grants.sql`은 다음 질문 API가 질문을 생성·갱신할 수 있도록 런타임 역할에 `questions` INSERT/UPDATE를 부여합니다. `006_records_material.sql`은 `records.material` 컬럼을 추가합니다. `007_profiles_and_regions.sql`은 `profiles`·RLS·런타임 권한과 내 기록 목록용 인덱스를 만들고 시연 지역 용인을 시드합니다. `008_support_programs.sql`은 지역 상하 관계와 `support_programs`·RLS·런타임 권한을 추가하고, `009_support_program_seed.sql`은 공식 원문으로 확인한 주거 지원 공고 4건을 중복 없이 시드합니다.

IPv4 네트워크에서는 대시보드 **Connect → Session pooler**의 호스트와 5432 포트를 사용합니다. 전용 역할의 풀러 사용자 이름은 `career_pair_runtime.<project-ref>`이며 `sslmode=require`를 붙입니다. 호스트의 `aws-0`/`aws-1` 부분은 프로젝트 연결 정보에 맞춰야 합니다. [공식 연결 문서](https://supabase.com/docs/guides/database/connecting-to-postgres)를 참고하세요.

현재 개발 환경은 **Home Keeper** (`lprqztpobrlhetbjkcks`, Sydney)에 연결되어 있습니다. 마이그레이션 001–005와 런타임 로그인 설정은 적용 완료했으며, 005의 `questions` INSERT/UPDATE 권한과 RLS 정책을 실제 DB에서 확인했습니다. `006_records_material.sql`, `007_profiles_and_regions.sql`, `008_support_programs.sql`, `009_support_program_seed.sql`은 이번 구현에 추가했지만 관리자 비밀번호가 저장되어 있지 않아 **Home Keeper에는 아직 적용하지 않았습니다.** 006 적용 전에는 `material` 컬럼을 참조하는 조회·수정·분석이, 007 적용 전에는 프로필·지역·기록 목록 API가, 008·009 적용 전에는 소식지 API가 실제 Supabase에서 실패합니다. 관리자 연결로 006–009를 순서대로 적용해야 합니다. 인증은 ES256/JWKS를 사용하므로 `SUPABASE_JWT_SECRET`은 비워 둡니다. 실제 Supabase에 테스트 스위트의 `TEST_ADMIN_DATABASE_URL`을 지정하지 마세요.

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

일괄 분석은 사진 1·2장 정상 저장/재조회, `material` 저장, 다른 사용자 접근 404, 사진 없음·3장·잘못된 형식·10MB 초과·역할 불일치 422, 같은 입력 재분석 시 버전 유지, 분석 중 입력 변경 409, 동시 분석의 입력/진단 혼합 방지, 샘플 결과에 bbox·confidence가 없음을 검증합니다. 프로필·지역·내 기록 목록은 사용자별 프로필 격리, 최초 등록·수정·upsert 재시도, 역할 변경 거부·업체 역할 보존, 닉네임·지역·거주 형태 검증, 용인 지역 시드, 본인 기록만 최근 수정순 요약 반환, 진단 없는 기록의 `null`/빈 배열 처리를 검증합니다. 소식지는 프로필 지역·상위 지역·전국 포함, 다른 지역 제외, 거주 형태 정렬, 한국 시간 마감 경계, 상시·기한 불명 구분, 상세·빈 목록·프로필 미등록·없는 공고, URL CHECK, 시드 반복, 동기화 upsert, API 키 미설정, 페이지 중간 실패·잘못된 응답 시 기존 데이터 보존을 검증합니다. 백엔드 전체 테스트 96개가 통과했습니다.

모바일 타입 검사:

```bash
npm run typecheck --workspace @career-pair/mobile
```

Expo Router 타입 생성 후 통과했습니다. 실제 기기/시뮬레이터에서 Supabase 로그인 후 프로필 저장·사진 선택·제출·결과 표시·기록 재열람 흐름은 이번 환경에서 실행하지 못했습니다. Home Keeper에는 006–009 마이그레이션이 아직 적용되지 않아 실제 Supabase 대상 분석·프로필·목록·소식지 호출도 검증하지 못했습니다.

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
- 실제 `GOV24_API_KEY`로 `serviceList` **10,891건**을 조회하고, 주거 제목 필터·지역 확정 후 **41건을 로컬 개발 DB에 upsert**하는 것까지 확인했습니다. Home Keeper에는 `support_programs` 마이그레이션이 아직 없어 실제 Supabase 동기화는 별도 적용 후 가능합니다. 운영 응답의 주거 키워드·지역·기한 해석은 첫 실동기화 결과를 계속 점검해야 합니다.

## API 동작

공통 오류 형식:

```json
{ "code": "revision_conflict", "message": "입력이 변경되었어요...", "input_revision": 2 }
```

| 상황 | 상태 |
| --- | --- |
| 인증 없음/서명·만료·발급자·대상 오류 | 401 |
| 없는 기록, 다른 사용자 기록, 없는 질문, 없는 메시지, assistant 메시지 수정, 미등록 프로필, 없는 지원 사업 | 404 |
| `input_revision` 충돌, 분석 중 입력 변경, 같은 `client_message_id`의 다른 내용 | 409 |
| 요청 형식, 없는 선택지, 잘못된 사진 형식·개수·크기·역할, 프로필의 닉네임·지역·거주 형태, 잘못된 소식지 `status` | 422 |
| 예기치 않은 서버/DB 오류 | 500 |

기록의 `input_revision`은 0에서 시작합니다. 위치·재질·증상, 사용자 메시지 추가, 사용자 메시지 내용 수정, 일괄 분석의 입력 변경처럼 실제 입력이 바뀔 때만 1씩 증가합니다. 같은 값을 다시 저장하거나 같은 메시지를 재전송하거나 같은 입력으로 다시 분석하면 증가하지 않습니다. 분석은 성공할 때마다 `diagnosis_generation`을 올립니다.

`GET /records/{record_id}` 응답의 `diagnosis`, `next_question`, `drafts`에는 생성 당시 `input_revision`(과 요청문의 경우 `diagnosis_generation`)과 `is_current`가 들어 있습니다. 입력이 바뀐 뒤에는 `is_current`가 false이므로 앱이 이전 결과임을 표시할 수 있습니다.

질문과 메시지는 `records.conversation_sequence`에서 순서를 함께 발급받습니다. 두 테이블의 `sequence`를 합쳐 정렬하면 기록 안의 대화 순서가 안정적으로 유지됩니다. 과거 사용자 메시지를 수정하면 그 `sequence`보다 큰 메시지와 질문을 같은 트랜잭션에서 삭제합니다.

### 호출 예시

아래는 로컬 개발용입니다. `MIGRATION_DATABASE_URL`이 설정되어 있고, `USER_ID`에 해당하는 행이 `auth.users`에 있어야 합니다. `jq`와 `uuidgen`을 사용합니다.

```bash
USER_ID=11111111-1111-1111-1111-111111111111
psql "$MIGRATION_DATABASE_URL" \
  -c "INSERT INTO auth.users (id) VALUES ('$USER_ID') ON CONFLICT DO NOTHING"

ACCESS_TOKEN=$(uv run --directory apps/api python - <<PY
import jwt
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
print(jwt.encode({
    "sub": "$USER_ID",
    "aud": "authenticated",
    "iss": "http://127.0.0.1:54321/auth/v1",
    "iat": now,
    "exp": now + timedelta(minutes=10),
    "role": "authenticated",
}, "change-me-jwt-secret", algorithm="HS256"))
PY
)
```

위 토큰은 `apps/api/.env`의 `SUPABASE_URL=http://127.0.0.1:54321`, `SUPABASE_JWT_SECRET=change-me-jwt-secret`로 서버를 띄웠을 때만 유효합니다. 실제 Supabase에서는 로그인 응답의 `access_token`을 사용합니다.

프로필을 먼저 등록합니다. `GET /regions`에서 받은 지역 ID를 사용하며, 같은 사용자로 `PUT /me/profile`을 다시 호출하면 한 프로필만 수정됩니다. 요청에 `role`이나 `user_id`를 넣지 않습니다.

```bash
REGION_ID=$(curl -s http://127.0.0.1:8000/regions \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.[0].region_id')

curl -s -X PUT http://127.0.0.1:8000/me/profile \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"nickname\": \"하자탐정\",
    \"region_id\": \"$REGION_ID\",
    \"address\": \"용인시 수지구\",
    \"housing_type\": \"monthly_rent\"
  }"

curl -s http://127.0.0.1:8000/me/profile \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

프로필이 없을 때 `GET /me/profile`은 404를 반환합니다. 새 프로필의 역할은 서버가 `requester`로 정하며, 기존 업체 계정의 `provider` 역할은 이 API로 바뀌지 않습니다.

소식지는 프로필의 거주 지역·상위 지역·전국 공고를 반환합니다. `status=active`는 마감된 공고를 제외합니다.

```bash
curl -s http://127.0.0.1:8000/support-programs \
  -H "Authorization: Bearer $ACCESS_TOKEN"

PROGRAM_ID=$(curl -s "http://127.0.0.1:8000/support-programs?status=active" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.[0].id')

curl -s "http://127.0.0.1:8000/support-programs/$PROGRAM_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

목록 항목에는 `housing_type_matched`, `deadline_text`, `deadline_date`, `deadline_kind`, `is_closed`, `source_attribution`, `source_checked_at`이 들어갑니다. 상세에는 지원 대상·내용·선정 기준·신청 방법과 `source_checked_at`·`synced_at`이 추가됩니다. 공고 데이터를 직접 수정하는 API는 없습니다.

```bash
RECORD_ID=$(curl -s -X POST http://127.0.0.1:8000/records \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r .record_id)

curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"client_message_id\": \"$(uuidgen | tr 'A-Z' 'a-z')\",
    \"content\": \"창틀 아래에 곰팡이가 있어요\",
    \"input_revision\": 0
  }"

curl -s "http://127.0.0.1:8000/records/$RECORD_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -s http://127.0.0.1:8000/records \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

마지막 `GET /records`는 본인 기록을 최근 수정순으로 요약한 배열입니다. 각 항목에는 `record_id`, 위치·재질·증상, `suspected_types`, `severity_score`, `severity_level`, 생성·수정 시각이 들어가며 전체 진단과 대화는 포함하지 않습니다. 앱의 `내 정보` 화면은 이 목록을 표시하고 항목을 누르면 `GET /records/{record_id}` 결과 화면으로 이동합니다.

선택 답변은 `content` 대신 `selected_option_id`와 `question_id`를 보냅니다. 서버가 질문의 선택지인지 확인한 뒤 저장된 `label`을 본문으로 씁니다.

```json
{
  "client_message_id": "8a5f2f4e-2c1b-4a3a-9b8e-1d2f3a4b5c6d",
  "question_id": "<question UUID>",
  "selected_option_id": "recurred",
  "input_revision": 1
}
```

같은 `client_message_id`와 같은 내용을 다시 보내면 기존 메시지를 반환합니다. 같은 ID에 다른 내용(또는 다른 질문·선택지)을 보내면 409입니다. 비교에는 최초 POST의 선택지 ID와 직접 입력을 사용하므로 같은 label의 다른 선택지와 직접 입력도 구분합니다. PUT으로 수정한 뒤 원래 POST를 재전송하면 수정된 현재 메시지를 반환합니다. `002_message_submission.sql` 이전 메시지는 최초 제출 방식을 복원할 수 없어 재전송 시 409를 반환하므로 기록을 다시 조회해야 합니다.

### 사진·위치·재질 일괄 분석 (샘플)

`POST /records/{record_id}/analyze`는 multipart/form-data로 사진 1~2장, 사진 역할, 위치, 재질, 선택 증상 메모, 외부 분석 동의 여부를 받습니다. 현재는 실제 사진 분석·LLM을 호출하지 않고 입력값 기반 샘플 결과를 저장합니다.

```bash
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/analyze" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "photos=@/path/to/overview.jpg;type=image/jpeg" \
  -F "photo_roles=overview" \
  -F "external_analysis_consent=false" \
  -F "location=안방 창틀 아래" \
  -F "material=실리콘" \
  -F "symptoms=닦아도 검은 얼룩이 다시 생겨요"

curl -s "http://127.0.0.1:8000/records/$RECORD_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

두 장을 보낼 때는 `photos`와 `photo_roles`를 각각 두 번 보내고 역할을 `overview`, `closeup`으로 구분합니다. 사진 수와 역할 수가 같아야 하며 역할은 중복될 수 없습니다. JPEG·PNG·HEIC·HEIF, 한 장당 10MB 이하만 허용합니다.

응답과 `GET /records/{record_id}`의 `photo_observations`에는 `source="sample"`, `applied=false`, 사진 상태 `not_analyzed`, `detections=[]`가 들어갑니다. 탐지 좌표·신뢰도는 만들지 않으며 원본 사진은 DB·로그에 저장하지 않습니다. 진단의 `source`도 `sample`이고, 심각도·추정 원인·해결방안·재발 방지책은 입력값만 사용한 참고용 결과입니다. 입력이 실제로 바뀌면 `input_revision`이 오르고 `diagnosis_generation`이 증가하며, 분석 중 입력이 바뀌면 409를 반환합니다.

모바일은 `apps/mobile/src/app/analyze.tsx`에서 사진 선택·입력·동의를 받아 기록 생성 후 분석을 호출하고, `apps/mobile/src/app/result/[recordId].tsx`에서 저장된 결과를 다시 조회해 표시합니다. FormData 전송 시 `Content-Type`을 직접 지정하지 않아 fetch가 boundary를 설정합니다.

`POST /records/{record_id}/next-question`는 현재 서버의 입력과 대화만 사용하며, 클라이언트가 사용자 ID나 대화 전체를 다시 보내지 않습니다. 질문·선택지는 서버가 `source="sample"`로 표시해 반환합니다. 실제 LLM이 아니라 아래 두 질문을 사용하는 시연 규칙입니다.

### 시연용 다음 질문 흐름 (현재 코드 · MVP 미사용/보류 레거시)

> 참고: 2026년 11월 20일 변경으로 분석 페이지의 AI 채팅창이 제거되어 현재 MVP 흐름에서는 아래 `messages`·`next-question` API를 호출하지 않습니다. 현재 저장소에 구현·테스트된 레거시/보류 동작을 확인하기 위한 예시입니다.

기록 생성 → 위치·증상 저장 → 첫 질문 → 답변 → 다음 질문 → 종료 순서입니다. 아래 예시는 `location`·`symptoms`를 먼저 저장하고 첫 질문을 받습니다.

```bash
RECORD_ID=$(curl -s -X POST http://127.0.0.1:8000/records \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r .record_id)

curl -s -X PATCH "http://127.0.0.1:8000/records/$RECORD_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"location":"안방 창틀 아래","symptoms":"검은 곰팡이 의심 얼룩"}'

FIRST=$(curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/next-question" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$FIRST"   # source=sample, 첫 질문, input_revision=1
Q1_ID=$(echo "$FIRST" | jq -r .question.id)

curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"client_message_id\": \"$(uuidgen | tr 'A-Z' 'a-z')\",
    \"question_id\": \"$Q1_ID\",
    \"selected_option_id\": \"recurred\",
    \"input_revision\": 1
  }"

SECOND=$(curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/next-question" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$SECOND"  # 두 번째 질문, input_revision=2
Q2_ID=$(echo "$SECOND" | jq -r .question.id)

curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"client_message_id\": \"$(uuidgen | tr 'A-Z' 'a-z')\",
    \"question_id\": \"$Q2_ID\",
    \"selected_option_id\": \"ventilated\",
    \"input_revision\": 2
  }"

curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/next-question" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# question=null, ready_for_diagnosis=true, source="sample", input_revision=3
```

시연 질문은 곰팡이 의심 창가 얼룩 사례의 두 가지 정보만 확인합니다. 지원 하자 유형 전체를 확정한 규칙이 아닙니다.

| 순서 | 질문 | 선택지 ID |
| --- | --- | --- |
| 1 | 닦은 뒤 같은 흔적이 다시 생겼나요? | `recurred`, `first_seen`, `unknown` |
| 2 | 이미 어떤 조치를 했나요? | `wiped`, `ventilated`, `none`, `unknown` |

직접 입력은 명확히 대응할 수 있는 문구만 규칙으로 처리합니다.

- 1번: `다시 생겼`, `또 생겼`, `다시 나타났`, `또 나타났`, `재발` → `recurred`; `처음 발견`, `처음 생`, `처음 봤` → `first_seen`; `모르` → `unknown`
- 2번: `닦아봤`, `닦았` → `wiped`; `환기했`, `환기를 했` → `ventilated`; `아무것도`, `아무 조치` → `none`; `모르` → `unknown`
- 그 밖의 문장은 답변으로 확정하지 않고 짧은 반응과 함께 같은 질문을 다시 반환합니다.
- `unknown`은 “질문을 닫았다”는 뜻으로만 `answered=true`가 되며, 확인된 사실로 사용하지 않습니다. 새 질문이 없으면 같은 입력 버전의 완료 응답을 재사용하고, `reply=null`, `question=null`인 종료 응답도 저장합니다.

질문 생성은 실제 모델 호출이 아니라 `apps/api/app/sample_questions.py`의 작은 결정 함수입니다. 이후 LLM으로 교체할 지점은 이 함수이며, 나머지 질문·메시지 저장과 버전 검사는 그대로 재사용합니다. 테스트 fixture의 질문은 기존 메시지 API 회귀 테스트에만 사용합니다.

## 구현 메모와 한계

- JWT는 PyJWT로 서명, `exp`, `iat`, `iss`, `aud`, `sub`(UUID)를 검증합니다. 디코딩만 한 토큰의 사용자 ID는 신뢰하지 않습니다. `sub`가 소유자입니다.
- 쓰기 요청은 기록 행을 `FOR UPDATE`로 잠가 한 기록의 버전·순서 갱신을 직렬화합니다. 조회는 `REPEATABLE READ` 스냅샷을 사용합니다.
- 메시지 재전송은 소유권 확인 뒤, 버전 확인 전에 기존 `client_message_id`를 조회합니다. 최초 저장으로 버전이 올라간 뒤에도 재전송이 성공합니다.
- 과거 메시지 수정은 기록 소유권 확인 후, 대상 메시지 조회보다 먼저 `input_revision`을 검사합니다. 오래된 버전이면 메시지가 없어도 최신 버전을 포함한 409를 반환하며, 버전이 일치할 때 대상이 없으면 404입니다. 내용이 같으면 삭제와 버전 증가 없이 성공을 반환하고, 내용이 달라질 때만 이후 메시지·질문을 삭제합니다. 이때 수정한 답변의 질문은 `answered=false`로 되돌리고 `next_question` 캐시도 지웁니다.
- `POST /records/{record_id}/next-question`은 실제 LLM 없이 `app/sample_questions.py`의 두 질문 규칙으로 동작합니다. 입력 스냅샷으로 결정하고, 저장 직전에 기록 행을 다시 잠가 `input_revision`과 기존 완료 응답을 재확인합니다. 질문·AI 응답·`answered` 변경·완료 응답은 한 트랜잭션에 저장하며 `input_revision`은 올리지 않습니다. 같은 버전의 저장 응답은 재생성하지 않고 반환합니다.
- `PATCH /records/{record_id}`는 [API 설계](docs/design/API_DESIGN.md)대로 `input_revision`을 받지 않습니다. 실제 값이 바뀔 때만 버전을 올리고, 명시한 `null`은 값을 지웁니다.
- 마이그레이션은 로컬 개발을 위해 `auth.users(id)` 스텁을 만들 수 있게 했습니다. Supabase에서는 기존 테이블이 그대로 쓰입니다.
- Supabase의 런타임 DB 연결·RLS·Data API 권한 회수와 ES256 JWKS 조회를 확인했습니다. 실제 사용자 로그인 토큰을 이용한 전체 인증 흐름은 아직 검증하지 않았습니다. 통합 테스트는 로컬 PostgreSQL과 HS256 토큰으로 실행합니다. `005_next_question_grants.sql`은 Home Keeper에 적용했고 적용 이력과 질문 INSERT/UPDATE 권한을 확인했습니다.
- `POST /records/{record_id}/analyze`는 사진과 입력을 multipart로 받아 샘플 결과를 저장합니다. 실제 YOLO·비전 LLM·텍스트 LLM은 호출하지 않고, 사진은 magic byte 검증만 하며 원본·좌표·신뢰도를 저장하지 않습니다. 입력 스냅샷으로 결과를 만든 뒤 저장 직전에 `input_revision`을 재확인하고, 사진 관찰 상태·진단 결과와 `diagnosis_generation`을 같은 트랜잭션에 저장합니다.
- 회원 프로필 API·화면, 거주 형태, 내 기록 목록과 과거 결과 재열람, 주거 지원 사업 소식지 백엔드(목록·상세·검증 시드·보조금24 수동 동기화)는 구현했습니다. 소식지 모바일 화면, 실제 모델 기반 사진 분석·진단 재생성, 사진 원본·표시 좌표·스토리지, 요청문 생성, 업체 검색·1:1 채팅, 회원가입 화면과 4개 탭은 아직 구현하지 않았습니다. 현재 `next-question` 코드의 시연 규칙은 곰팡이 의심 창가 얼룩의 두 질문만 처리하는 레거시/보류 구현이며, 변경된 MVP의 지원 하자 유형은 `크랙·벗겨짐·곰팡이`, 시연 지역은 `용인`입니다.
- `records.material`을 추가하는 `006_records_material.sql`, `profiles`·용인 지역 시드를 추가하는 `007_profiles_and_regions.sql`, 지역 상하 관계·지원 사업을 추가하는 `008_support_programs.sql`, 검증 시드 `009_support_program_seed.sql`은 로컬 테스트 DB와 로컬 개발 DB(`career_pair_dev`)에 적용했지만 Home Keeper에는 관리자 자격증명이 없어 아직 적용하지 않았습니다. 006 적용 전에는 실제 Supabase에서 `material`을 참조하는 조회·수정·분석이, 007 전에는 프로필·지역·기록 목록 API가, 008·009 전에는 소식지 API가 실패합니다.
- 보조금24 동기화는 실제 `GOV24_API_KEY`로 `serviceList` 10,891건을 조회하고 주거 제목 필터·지역 확정 후 41건을 로컬 개발 DB에 upsert하는 것까지 확인했습니다. Home Keeper에는 008·009 마이그레이션이 없어 실제 Supabase 동기화는 아직 실행하지 못했습니다. 운영 응답의 주거 키워드·지역명·기한 문구는 첫 적용 후 계속 점검해야 합니다.
- 모바일 앱은 이메일 로그인, 프로필 등록·수정, 내 기록 목록, 사진 1~2장 선택, 위치·재질·증상·외부 분석 동의 입력, 기록 생성 후 샘플 분석 호출, 결과 화면(심각도·추정 원인·해결방안·재발 방지책·샘플 안내·재시도)까지 구현했습니다. 실제 기기/시뮬레이터에서 Supabase 로그인과 API 호출은 아직 검증하지 못했습니다. FormData 요청은 `Content-Type`을 직접 지정하지 않습니다.
