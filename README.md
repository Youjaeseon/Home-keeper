# Career Pair 백엔드 (MVP)

하자 기록과 대화 메시지를 사용자별로 저장하는 FastAPI + PostgreSQL 백엔드입니다. 인증은 Supabase Auth 액세스 토큰을 사용합니다.

구현된 API는 `POST /records`, `GET /records/{record_id}`, `PATCH /records/{record_id}`, `POST /records/{record_id}/messages`, `PUT /records/{record_id}/messages/{message_id}` 다섯 개입니다. 사진 분석, 다음 질문·진단·요청문 생성, 업체 검색, 앱 화면은 이번 범위가 아니며 DB 컬럼만 준비되어 있습니다.

## 문서 안내

팀 전체 흐름은 MVP 계획부터, 백엔드 구현과 앱 연동은 이 README와 API 설계부터 읽습니다.

| 문서 | 확인할 내용 |
| --- | --- |
| [MVP 계획](docs/plans/MVP_PLAN.md) | 사용자 흐름, 역할, 시연 범위와 남은 제품 결정 |
| [백엔드 설계](docs/design/BACKEND_DESIGN.md) | 인증, 기록·대화 처리, 버전 검사와 모델 연동 규칙 |
| [DB 설계](docs/design/DB_DESIGN.md) | 테이블·제약·인덱스와 실제 마이그레이션에서 확정한 내용 |
| [API 설계](docs/design/API_DESIGN.md) | 현재 API 계약과 후속 API 계획, 요청·응답 예시 |
| [용어집](GLOSSARY.md) | 하자 기록, 점검 요청, 견적 요청문의 의미 |
| [프로젝트 계획](docs/plans/PROJECT_PLAN.md) | 제출 요건, 전체 일정, 검증표와 결정 이력 |
| [AI 아이디어 비교](docs/ideas/AI_IDEAS.md) | 후속 기능 후보와 검토 근거 |

현재 구현은 기록·메시지 API와 DB 기반입니다. 설계 문서에 있는 사진 분석, 질문·진단·요청문 생성, 업체 검색은 후속 구현 대상입니다. 실행·환경 설정은 이 README를, 적용된 DB 구조는 [마이그레이션](migrations/)을 함께 확인합니다.

## 구조

```text
pyproject.toml     uv 프로젝트와 의존성
uv.lock            잠금 파일
.python-version    Python 3.13
app/
  main.py          FastAPI 앱, 오류 응답
  auth.py          Supabase JWT 검증
  records.py       기록·메시지 API
  schemas.py       요청·응답 모델
  db.py            요청별 DB 트랜잭션
  migrate.py       SQL 마이그레이션 실행기
  config.py        환경변수
migrations/        순서대로 적용하는 SQL 마이그레이션
tests/             실제 PostgreSQL 통합 테스트
docs/
  plans/           MVP·프로젝트 계획
  design/          백엔드·DB·API 설계
  ideas/           AI 기능 후보 비교
.env.example
```

이 저장소는 uv 프로젝트입니다. 의존성은 `pyproject.toml`, 잠금은 `uv.lock`이 관리하며, 아래 명령은 모두 저장소 루트에서 실행합니다.

## 준비

- Python 3.11 이상, [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 이상
- Supabase 프로젝트(인증용) 또는 로컬 테스트용 JWT

```bash
uv sync
cp .env.example .env
```

`uv`가 `.python-version`(3.13)의 Python과 `.venv`를 관리합니다. 잠금 파일 기준으로 정확히 설치하려면 `uv sync --locked`를 사용합니다.

- 의존성 추가: `uv add <package>`
- 개발 의존성 추가: `uv add --dev <package>`
- 잠금 갱신: `uv lock`
- 명령 실행: `uv run <command>`

`.venv/`와 `.env`는 생성물이므로 커밋하지 않습니다.

### 환경변수

| 변수 | 필수 | 설명 |
| --- | --- | --- |
| `DATABASE_URL` | 예 | FastAPI 런타임 연결. `career_pair_runtime`처럼 DML 권한만 가진 계정 |
| `MIGRATION_DATABASE_URL` | 마이그레이션 시 | 테이블·역할·권한을 만드는 관리자 연결 |
| `SUPABASE_URL` | 예 | `https://<project-ref>.supabase.co`. 발급자는 여기에 `/auth/v1`을 붙인 값 |
| `SUPABASE_JWT_SECRET` | HS256 토큰만 | 기존 Supabase JWT secret. 비대칭 서명 키를 쓰면 비워 둔다 |
| `SUPABASE_JWT_AUDIENCE` | 아니오 | 기본 `authenticated` |
| `SUPABASE_JWT_ISSUER` | 아니오 | 기본 `SUPABASE_URL + /auth/v1`. 로컬 Supabase 등에서 재정의 |

`.env`는 커밋하지 않습니다.

## 로컬 PostgreSQL 설정

```bash
createdb career_pair

MIGRATION_DATABASE_URL=postgresql://localhost:5432/career_pair \
  uv run python -m app.migrate

# 마이그레이션이 만든 런타임 역할에 로그인 비밀번호를 지정한다.
psql postgresql://localhost:5432/career_pair \
  -c "ALTER ROLE career_pair_runtime LOGIN PASSWORD 'change-me'"
```

`.env`의 `DATABASE_URL`을 `postgresql://career_pair_runtime:change-me@localhost:5432/career_pair`로 맞춥니다.

마이그레이션은 `schema_migrations`에 적용 이력을 남기므로 다시 실행해도 완료된 파일은 건너뜁니다. 관리자 연결은 테이블과 역할을 만들고, 런타임 연결은 이번 API에 필요한 권한만 가집니다: 기록 `SELECT/INSERT/UPDATE`, 질문 `SELECT/DELETE`, 메시지 `SELECT/INSERT/UPDATE/DELETE`, 업체·지역·작업 참조 테이블 `SELECT`. 런타임 역할은 `auth.users`를 읽거나 DDL을 실행할 수 없습니다. 새 기능이 더 많은 권한을 필요로 하면 새 마이그레이션에서 명시적으로 부여합니다.

### Supabase 사용 시

1. Supabase의 **direct connection**(풀러가 아닌 5432 포트) 관리자 자격증명으로 마이그레이션을 실행합니다.
   ```bash
   MIGRATION_DATABASE_URL='postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres' \
     uv run python -m app.migrate
   ```
   Supabase에는 이미 `auth.users`가 있으므로 `auth` 스키마에 DDL을 실행하지 않고, `records.owner_id` 외래키만 추가됩니다.
2. 런타임 역할의 비밀번호를 설정하고 `DATABASE_URL`에 Supabase 연결 문자열(`sslmode=require` 권장)을 넣습니다.
   ```sql
   ALTER ROLE career_pair_runtime LOGIN PASSWORD '<runtime-password>';
   ```
3. `SUPABASE_URL`과 JWT 설정을 채웁니다. 새 프로젝트가 비대칭 서명 키(`RS256`/`ES256`)를 쓰면 `SUPABASE_JWT_SECRET` 없이 JWKS(`/auth/v1/.well-known/jwks.json`)로 검증합니다. 기존 HS256 토큰이면 secret을 설정합니다.
4. 앱 테이블은 마이그레이션에서 Supabase Data API 역할(`anon`, `authenticated`, `service_role`)의 권한을 회수합니다. Supabase 대시보드의 Data API 노출 스키마에 별도 권한을 추가하지 마세요. 앱은 테이블을 직접 노출하지 않고 FastAPI를 통해서만 접근합니다.
5. `003_backend_rls.sql`은 앱 테이블의 RLS를 켜고 전용 `career_pair_runtime` 역할만 통과시킵니다. 사용자별 소유권 검사는 FastAPI가 담당하므로 이 DB 계정은 서버에서만 사용합니다. `schema_migrations`는 관리자만 접근합니다. `004_protect_rls_trigger.sql`은 Supabase 내부 RLS 이벤트 트리거가 있을 때 공개 실행 권한을 회수합니다.

IPv4 네트워크에서는 대시보드 **Connect → Session pooler**의 호스트와 5432 포트를 사용합니다. 전용 역할의 풀러 사용자 이름은 `career_pair_runtime.<project-ref>`이며 `sslmode=require`를 붙입니다. 호스트의 `aws-0`/`aws-1` 부분은 프로젝트 연결 정보에 맞춰야 합니다. [공식 연결 문서](https://supabase.com/docs/guides/database/connecting-to-postgres)를 참고하세요.

현재 개발 환경은 **Home Keeper** (`lprqztpobrlhetbjkcks`, Sydney)에 연결되어 있습니다. 초기 마이그레이션 001–004와 런타임 로그인 설정은 적용 완료했으며, `.env`에 실제 런타임 연결을 저장했습니다. 인증은 ES256/JWKS를 사용하므로 `SUPABASE_JWT_SECRET`은 비워 둡니다. 관리자 비밀번호는 저장하지 않았으므로 후속 마이그레이션을 CLI로 실행하려면 `MIGRATION_DATABASE_URL`을 별도로 설정해야 합니다. 실제 Supabase에 테스트 스위트의 `TEST_ADMIN_DATABASE_URL`을 지정하지 마세요.

## 실행

```bash
uv run uvicorn app.main:app --reload --env-file .env
```

- 상태 확인: `GET http://127.0.0.1:8000/health`
- API 문서: `http://127.0.0.1:8000/docs` (Scalar)

서버는 요청 본문, 비밀번호, 액세스 토큰을 로그에 남기지 않습니다. 기본 uvicorn 액세스 로그에는 메서드와 경로만 남습니다.

## 테스트

```bash
uv run pytest
```

테스트는 실제 PostgreSQL을 사용합니다. 기본값은 `postgresql://localhost:5432/postgres`에 현재 OS 사용자로 접속해 `career_pair_test` 데이터베이스를 **삭제 후 재생성**하고, 빈 DB에 마이그레이션을 적용한 뒤 런타임 역할로 API를 호출합니다. 다음 권한이 필요합니다.

- `CREATE DATABASE`, `DROP DATABASE`
- 역할 비밀번호 변경(`ALTER ROLE`)

다른 서버를 쓰려면:

```bash
TEST_ADMIN_DATABASE_URL=postgresql://user:pass@localhost:5432/postgres \
TEST_DATABASE_NAME=career_pair_ci_test \
  uv run pytest
```

`TEST_DATABASE_NAME`은 `_test`로 끝나야 하며, 운영 DB를 가리키는 이름은 거부합니다. 테스트는 클러스터의 `career_pair_runtime` 역할 비밀번호를 테스트 값으로 변경하므로 로컬 개발 클러스터에서만 실행하세요. 테스트는 실제 Supabase에 연결하지 않고 로컬에서 서명한 HS256 토큰을 사용합니다. 인증 경계는 FastAPI의 `app.dependency_overrides`로 대체할 수 있지만, 운영 코드에는 인증 우회 경로가 없습니다.

검증 항목: 빈 DB 마이그레이션, 서명·만료·발급자·대상 검증, 소유권 격리, 다른 기록 질문 거부, 선택지/직접 입력 저장, 메시지 재전송 멱등성, 동일 ID 내용 충돌, 오래된 버전 거부, 과거 메시지 수정 시 후속 대화 삭제, 동일 내용 수정 무변경, 동시 요청 중복·순서 방지, 수정 실패 시 롤백, DB 제약과 런타임 권한.

## API 동작

공통 오류 형식:

```json
{ "code": "revision_conflict", "message": "입력이 변경되었어요...", "input_revision": 2 }
```

| 상황 | 상태 |
| --- | --- |
| 인증 없음/서명·만료·발급자·대상 오류 | 401 |
| 없는 기록, 다른 사용자 기록, 없는 질문, 없는 메시지, assistant 메시지 수정 | 404 |
| `input_revision` 충돌, 같은 `client_message_id`의 다른 내용 | 409 |
| 요청 형식, 없는 선택지 | 422 |
| 예기치 않은 서버/DB 오류 | 500 |

기록의 `input_revision`은 0에서 시작합니다. 위치·증상, 사용자 메시지 추가, 사용자 메시지 내용 수정처럼 실제 입력이 바뀔 때만 1씩 증가합니다. 같은 값을 다시 저장하거나 같은 메시지를 재전송하면 증가하지 않습니다.

`GET /records/{record_id}` 응답의 `diagnosis`, `next_question`, `drafts`에는 생성 당시 `input_revision`(과 요청문의 경우 `diagnosis_generation`)과 `is_current`가 들어 있습니다. 입력이 바뀐 뒤에는 `is_current`가 false이므로 앱이 이전 결과임을 표시할 수 있습니다.

질문과 메시지는 `records.conversation_sequence`에서 순서를 함께 발급받습니다. 두 테이블의 `sequence`를 합쳐 정렬하면 기록 안의 대화 순서가 안정적으로 유지됩니다. 과거 사용자 메시지를 수정하면 그 `sequence`보다 큰 메시지와 질문을 같은 트랜잭션에서 삭제합니다.

### 호출 예시

아래는 로컬 개발용입니다. `MIGRATION_DATABASE_URL`이 설정되어 있고, `USER_ID`에 해당하는 행이 `auth.users`에 있어야 합니다. `jq`와 `uuidgen`을 사용합니다.

```bash
USER_ID=11111111-1111-1111-1111-111111111111
psql "$MIGRATION_DATABASE_URL" \
  -c "INSERT INTO auth.users (id) VALUES ('$USER_ID') ON CONFLICT DO NOTHING"

ACCESS_TOKEN=$(uv run python - <<PY
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

위 토큰은 `.env`의 `SUPABASE_URL=http://127.0.0.1:54321`, `SUPABASE_JWT_SECRET=change-me-jwt-secret`로 서버를 띄웠을 때만 유효합니다. 실제 Supabase에서는 로그인 응답의 `access_token`을 사용합니다.

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
```

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

테스트 fixture가 아닌 공개 질문 생성 API는 없습니다. 이번 범위에서 질문·선택지는 `tests/conftest.py`의 `question_factory`처럼 DB에 직접 준비합니다.

## 구현 메모와 한계

- JWT는 PyJWT로 서명, `exp`, `iat`, `iss`, `aud`, `sub`(UUID)를 검증합니다. 디코딩만 한 토큰의 사용자 ID는 신뢰하지 않습니다. `sub`가 소유자입니다.
- 쓰기 요청은 기록 행을 `FOR UPDATE`로 잠가 한 기록의 버전·순서 갱신을 직렬화합니다. 조회는 `REPEATABLE READ` 스냅샷을 사용합니다.
- 메시지 재전송은 소유권 확인 뒤, 버전 확인 전에 기존 `client_message_id`를 조회합니다. 최초 저장으로 버전이 올라간 뒤에도 재전송이 성공합니다.
- 과거 메시지 수정은 기록 소유권 확인 후, 대상 메시지 조회보다 먼저 `input_revision`을 검사합니다. 오래된 버전이면 메시지가 없어도 최신 버전을 포함한 409를 반환하며, 버전이 일치할 때 대상이 없으면 404입니다. 내용이 같으면 삭제와 버전 증가 없이 성공을 반환하고, 내용이 달라질 때만 이후 메시지·질문을 삭제합니다.
- `PATCH /records/{record_id}`는 [API 설계](docs/design/API_DESIGN.md)대로 `input_revision`을 받지 않습니다. 실제 값이 바뀔 때만 버전을 올리고, 명시한 `null`은 값을 지웁니다.
- 마이그레이션은 로컬 개발을 위해 `auth.users(id)` 스텁을 만들 수 있게 했습니다. Supabase에서는 기존 테이블이 그대로 쓰입니다.
- Supabase의 런타임 DB 연결·RLS·Data API 권한 회수와 ES256 JWKS 조회를 확인했습니다. 실제 사용자 로그인 토큰을 이용한 전체 인증 흐름은 아직 검증하지 않았습니다. 통합 테스트는 로컬 PostgreSQL과 HS256 토큰으로 실행합니다.
- 사진 원본·표시 좌표·스토리지, 샘플 업체 저장, 질문/진단/요청문 생성, 업체 검색은 구현하지 않았습니다.
