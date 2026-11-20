# Home Keeper — 주거 하자 분석·대응 앱 (Career Pair MVP)

거주자(주로 청년 임차인)가 주거 하자(`크랙·벗겨짐·곰팡이`)의 사진·위치·재질을 입력하면 심각도와 대응 방안을 안내받고, 지역 주거 지원 사업 소식지와 과거 기록을 함께 관리하는 FastAPI + Expo 모노레포 프로젝트입니다. 인증은 Supabase Auth(이메일·비밀번호)를 사용하며 시연 지역은 용인입니다.

## 주요 기능

- **회원 인증·프로필**: Supabase 이메일 로그인, 닉네임·거주 지역·선택 등록 주소·거주 형태(`월세·전세·반전세·자가·기타`) 등록·수정
- **하자 일괄 분석·결과**: 사진(1~2장)·위치·재질·증상 메모 일괄 제출, 심각도·추정 원인·해결방안·재발 방지책 조회 *(현재 샘플 분석 구현)*
- **내 분석 기록**: 본인 하자 기록 목록 조회 및 과거 분석 결과 재열람
- **주거 지원 사업 소식지**: 공공데이터포털 보조금24 Open API 수동 동기화 + 검증 시드 기반 지역/전국 공고 조회 및 마감 정렬 *(백엔드 구현 완료)*
- **요청문·업체 검색·1:1 채팅**: 저장된 진단 기반 임대인 점검·업체 견적 요청문(LLM, 실패 시 기본 양식 폴백), 지역·작업 동시 일치 업체 검색, 하자 요약을 공유하는 요청인–업체 채팅 REST *(백엔드 구현 완료)*
- **후속 예정 기능**: 실제 YOLO·비전 LLM 연동, 요청문·업체 검색·채팅 모바일 화면, 실제 업체·계정 데이터, 실시간 채팅 수신, 모바일 소식지·회원가입·4개 탭

## 사용 기술

- **Backend**: Python 3.13 (`>=3.11`), FastAPI, PostgreSQL 16+, psycopg, PyJWT, Scalar, uv
- **Mobile**: Node.js 20+, React Native 0.88, Expo 58 (Expo Router), TypeScript 6
- **Auth & Data**: Supabase Auth, 공공데이터포털 보조금24 Open API

## 실행 환경

- Python 3.11 이상 (`apps/api/.python-version`: `3.13`), [uv](https://docs.astral.sh/uv/)
- Node.js 20 이상, npm
- PostgreSQL 16 이상 (로컬 DB 또는 Supabase)
- Supabase 프로젝트(인증용) 또는 로컬 테스트용 JWT
- Expo Go / iOS Simulator / Android Emulator (모바일 실행 시)

## 설치 및 실행 방법

1. **의존성 설치**
   ```bash
   npm install
   uv sync --directory apps/api
   ```
2. **환경변수 설정**
   ```bash
   cp apps/api/.env.example apps/api/.env
   cp apps/mobile/.env.example apps/mobile/.env
   ```
   필수 항목은 [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md#환경변수)를 참고해 입력합니다. 요청문 생성을 쓰려면 `LLM_API_KEY`(필요 시 `LLM_BASE_URL`·`LLM_MODEL`·`LLM_TIMEOUT_SECONDS`)를 설정합니다. 미설정 시 요청문 생성만 `503`이고 기본 양식 API는 계속 동작합니다.
3. **로컬 PostgreSQL DB 생성 및 마이그레이션**
   ```bash
   createdb career_pair
   MIGRATION_DATABASE_URL=postgresql://localhost:5432/career_pair \
     uv run --directory apps/api python -m app.migrate
   psql postgresql://localhost:5432/career_pair \
     -c "ALTER ROLE career_pair_runtime LOGIN PASSWORD 'change-me'"
   ```
   Supabase 연결 및 RLS 설정은 [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md#supabase-사용-시)를 참고하세요.
4. **백엔드·모바일 실행**
   ```bash
   npm run api
   npm run mobile
   ```
   상태 확인 `http://127.0.0.1:8000/health`, API 문서 `http://127.0.0.1:8000/docs` (Scalar). 실기기 `EXPO_PUBLIC_API_URL` 설정은 [실행 상세](docs/guides/DEVELOPMENT.md#실행-상세)를 참고하세요.
5. **테스트·타입 검사**
   ```bash
   npm run api:test
   npm run typecheck --workspace @career-pair/mobile
   ```

## 업체 계정·시연 데이터 준비

샘플 업체는 API가 빈 검색 결과에서만 반환하는 고정 시연 후보이며 `providers` 테이블에 넣지 않습니다. 실제 업체를 검색·채팅에 쓰려면 팀이 확인한 업체명·전화번호와 Supabase Auth 업체 계정 UUID를 **관리자 SQL**로 연결합니다. 공개 관리 API는 없고 일반 가입자는 업체로 승격되거나 `account_user_id`를 연결할 수 없습니다.

```sql
INSERT INTO providers (name, phone, account_user_id)
VALUES ('<확인된 업체명>', '<확인된 전화번호>', '<provider auth user id>')
RETURNING id;

INSERT INTO provider_regions (provider_id, region_id)
SELECT '<provider id>', id FROM regions WHERE name = 'yongin';

INSERT INTO provider_work_types (provider_id, work_type_id)
SELECT '<provider id>', id FROM work_types WHERE name = '곰팡이 제거';
```

작업 종류 4건(`곰팡이 제거`, `균열 보수`, `벽지·도장 보수`, `원인 점검`)은 `010` 마이그레이션이 시드합니다. 실제 업체·연락처·출장 지역 데이터는 팀 확인 자료가 없어 아직 등록하지 않았고, 후보가 없으면 검색은 `is_sample=true` 샘플을 반환합니다. 앱 내 채팅은 `account_user_id`가 연결된 업체만 가능합니다(`chat_available=true`).

## 주요 명령어

| 명령어 | 동작 |
| --- | --- |
| `npm run api` | FastAPI 개발 서버 실행 (`0.0.0.0:8000`) |
| `npm run api:migrate` | SQL 마이그레이션 실행 (`MIGRATION_DATABASE_URL` 필요) |
| `npm run api:sync-support-programs` | 보조금24 Open API 주거 지원 사업 수동 동기화 |
| `npm run api:test` | 백엔드 PostgreSQL 통합 테스트 실행 (`132개`) |
| `npm run mobile` | Expo 개발 서버 실행 |
| `npm run typecheck --workspace @career-pair/mobile` | 모바일 TypeScript 검사 |

## 프로젝트 구조

```text
package.json            npm workspaces와 공통 실행 스크립트
GLOSSARY.md             서비스·도메인 용어 정의
apps/
  api/                  FastAPI 백엔드, SQL 마이그레이션, 통합 테스트
  mobile/               Expo Router 모바일 앱
docs/
  COMMIT_CONVENTION.md  커밋 메시지 규칙
  guides/               개발 환경·DB·테스트 및 API 사용 가이드
  plans/                MVP·프로젝트 계획 및 구현 체크리스트
  design/               백엔드·DB·API 설계
  ideas/                AI 기능 후보 비교
```

상세 파일 트리 및 의존성 추가 규칙은 [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md#상세-디렉토리-구조와-의존성-관리)를 확인하세요.

## 현재 상태와 남은 작업

- **구현 완료**: 백엔드 API 21개(기록 CRUD·일괄 샘플 분석·프로필·지역·소식지·요청문·업체 검색·채팅 + 보류 레거시 `messages`·`next-question`), DB 마이그레이션 `001`–`010`, 보조금24 수동 동기화 및 검증 시드 4건, 모바일 로그인·프로필·분석 입력·결과·기록 목록 화면, 백엔드 통합 테스트 132개 및 모바일 타입 검사 통과
- **남은 작업**: Home Keeper Supabase에 `006`–`010` 마이그레이션 적용 및 실기기/실제 로그인 토큰 검증, 요청문·업체 검색·채팅 모바일 화면, 실제 업체·계정 데이터와 `LLM_API_KEY` 연동 검증, 실시간 채팅 수신 방식 확정, 소식지 모바일 화면·회원가입·4개 탭, 실제 모델 기반 사진 분석·진단

## 문서 안내

| 문서 | 확인할 내용 |
| --- | --- |
| [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md) | 상세 디렉토리 구조, 환경변수, 로컬 DB/Supabase 설정, 테스트, 소식지 시드·동기화 |
| [API 사용 가이드](docs/guides/API_USAGE.md) | 공통 오류·버전 규칙, `curl` 호출 예시, 레거시 다음 질문 흐름, 구현 메모와 한계 |
| [백엔드 구현 체크리스트](docs/plans/BACKEND_CHECKLIST.md) | 구현된 기능, 남은 MVP 작업과 통합 검증 |
| [MVP 계획](docs/plans/MVP_PLAN.md) | 사용자 흐름, 역할, 시연 범위와 남은 제품 결정 |
| [백엔드 설계](docs/design/BACKEND_DESIGN.md) | 인증, 기록·일괄 분석·소식지·채팅 처리 규칙 |
| [DB 설계](docs/design/DB_DESIGN.md) | 테이블·제약·인덱스와 실제 마이그레이션에서 확정한 내용 |
| [API 설계](docs/design/API_DESIGN.md) | 현재 API 계약과 후속 API 계획, 요청·응답 예시 |
| [용어집](GLOSSARY.md) | 요청인, 업체, 거주 형태, 소식지, 주거 지원 사업, 하자 기록 등의 의미 |
| [프로젝트 계획](docs/plans/PROJECT_PLAN.md) | 제출 요건, 전체 일정, 검증표와 결정 이력 |
| [AI 아이디어 비교](docs/ideas/AI_IDEAS.md) | 후속 기능 후보와 검토 근거 |
| [커밋 규칙](docs/COMMIT_CONVENTION.md) | 커밋 메시지 형식, 타입·스코프 기준과 분리 원칙 |
| [마이그레이션](apps/api/migrations/) | 실제 DB에 적용하는 SQL 마이그레이션 (`001`–`010`) |

## 데이터 출처 및 라이선스

- 주거 지원 사업 소식지 동기화 데이터는 공공데이터포털 [행정안전부_대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do)(보조금24 Open API, 이용허락범위: 제한 없음) 및 확인된 지자체·복지로 공고를 기반으로 합니다. 출처 URL 목록은 [소식지 시드·보조금24 동기화](docs/guides/DEVELOPMENT.md#소식지-시드보조금24-동기화)에서 확인할 수 있습니다.
- 별도 `LICENSE` 파일은 아직 포함되어 있지 않습니다(해커톤 프로젝트).
