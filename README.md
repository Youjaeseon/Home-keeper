# Home Keeper — 주거 하자 분석·대응 앱 (Career Pair MVP)

거주자(주로 청년 임차인)가 주거 하자(`크랙·벗겨짐·곰팡이`)의 사진·위치·재질을 입력하면 심각도와 대응 방안을 안내받고, 지역 주거 지원 사업 소식지와 과거 기록을 함께 관리하는 FastAPI + Expo 모노레포 프로젝트입니다. 인증은 Supabase Auth(이메일·비밀번호)를 사용하며 시연 지역은 용인입니다.

## 주요 기능

- **회원 인증·프로필**: Supabase 이메일 로그인, 닉네임·거주 지역·선택 등록 주소·거주 형태(`월세·전세·반전세·자가·기타`) 등록·수정
- **하자 일괄 분석·결과**: 사진(1~2장)·위치·재질·증상 메모 일괄 제출, 심각도·추정 원인·해결방안·재발 방지책 조회 *(YOLO 탐지·Meta SAM 3.1 분할 연결, 진단 안내는 샘플)*
- **내 분석 기록**: 본인 하자 기록 목록 조회 및 과거 분석 결과 재열람
- **주거 지원 사업 소식지**: 공공데이터포털 보조금24 Open API 수동 동기화 + 검증 시드 기반 지역/전국 공고 조회 및 마감 정렬 *(백엔드 구현 완료)*
- **요청문·업체 검색·1:1 채팅**: 저장된 진단 기반 임대인 점검·업체 견적 요청문(LLM, 실패 시 기본 양식 폴백), 지역·작업 동시 일치 업체 검색, 하자 요약을 공유하는 요청인–업체 채팅 REST·WebSocket·방별 미읽음 수 *(백엔드 구현 완료)*
- **후속 예정 기능**: 사진 탐지 기반 진단 생성, 요청문·업체 검색·채팅 모바일 화면(WebSocket·읽음 호출 연결 포함), 실제 업체·계정 데이터, 모바일 소식지·회원가입·4개 탭

11월 21일 시안 검토에서 이메일·비밀번호 인증 유지, 프로필 사진 제외, 진단 신뢰도 필드 추가, WebSocket·채팅방별 미읽음 수 표시를 확정했습니다. WebSocket·미읽음 수는 백엔드에 구현했고, 진단 신뢰도는 정의가 정해질 때까지 추가하지 않았습니다. 소셜 로그인은 시간 여유 시 재검토하며, 비회원 열람·날짜 입력·사진 보관·업체 추천 연결·가상 업체 응답은 [프로젝트 계획의 검토 목록](docs/plans/PROJECT_PLAN.md#11월-21일-프론트-시안-검토)에 미정으로 분류했습니다.

## 사용 기술

- **Backend**: Python 3.13 (`>=3.11`), FastAPI, PostgreSQL 16+, psycopg, PyJWT, Scalar, uv
- **Mobile**: Node.js 20+, React Native 0.88, Expo 58 (Expo Router), TypeScript 6
- **Auth & External API**: Supabase Auth, 공공데이터포털 보조금24 Open API, OpenAI 호환 LLM API

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
   uv sync --directory apps/api --extra vision
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
   Supabase 연결·RLS와 업체 계정·시연 데이터 준비는 [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md#supabase-사용-시)([업체 계정 준비](docs/guides/DEVELOPMENT.md#업체-계정시연-데이터-준비))를 참고하세요.
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

## 주요 명령어

| 명령어 | 동작 |
| --- | --- |
| `npm run api` | FastAPI 개발 서버 실행 (`0.0.0.0:8000`) |
| `npm run api:migrate` | SQL 마이그레이션 실행 (`MIGRATION_DATABASE_URL` 필요) |
| `npm run api:sync-support-programs` | 보조금24 Open API 주거 지원 사업 수동 동기화 |
| `npm run api:test` | 백엔드 PostgreSQL 통합 테스트 실행 (`160개`) |
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

## YOLO·Meta SAM 3.1 연결

`models/best.pt`는 서버에만 두며 Git에 포함하지 않습니다. 현재 체크포인트는 `crack`, `paint_peel` 두 클래스를 탐지합니다.

- `apps/api/.env`에 `YOLO_MODEL_PATH=../../models/best.pt`를 설정합니다(`npm run api` 기준).
- Meta Model API 키는 서버 환경변수 `MODEL_API_KEY`에 설정합니다. 앱에는 키를 넣지 않습니다.
- `npm run api`로 실행하면 사진을 회전 보정한 뒤 YOLO로 탐지합니다. 외부 분석 동의가 있고 키가 설정된 경우에만 같은 사진과 탐지 박스를 SAM `sam-3.1`에 전송합니다.
- 탐지 박스는 원본 기준 반열린 `xyxy`이며, 마스크는 COCO RLE와 원본 기준 `bounds`로 저장합니다. 사진 원본은 저장하지 않습니다. 사진은 2,500만 픽셀 이하, 탐지는 사진당 신뢰도 높은 최대 16개입니다.
- SAM 실패·키 미설정·동의 없음은 탐지 항목의 `segmentation_status`에 표시하며 YOLO 결과는 보존합니다. YOLO 실행 실패는 `503`이며 새 결과를 저장하지 않습니다.
- [사진 분석 확인 화면](http://127.0.0.1:8000/vision-test)에서 로그인한 뒤 사진을 선택하면 원본과 YOLO 박스·SAM 마스크를 나란히 비교할 수 있습니다. 동의를 체크해야 SAM을 호출합니다. 결과는 본인 기록에 저장하고, 같은 기록 ID로 재분석하면 교체합니다. 브라우저 검증 화면은 JPEG·PNG를 받습니다.
- `YOLO_MODEL_PATH` 미설정 시 샘플 모드입니다. 심각도·원인·대응 안내는 아직 입력값 기반 샘플이며 사진 탐지 결과를 반영하지 않습니다. 모바일에서 마스크를 사진에 겹쳐 그리는 기능은 포함하지 않습니다.

공식 규격: [Meta SAM 박스 프롬프트](https://dev.meta.ai/docs/sam/segmenting), [SAM 파서](https://dev.meta.ai/docs/sam/client-libraries).

## 현재 상태와 남은 작업

- **구현 완료**: 백엔드 API(기록 CRUD·일괄 사진 분석·프로필·지역·소식지·요청문·업체 검색·채팅 REST·WebSocket·방별 미읽음 수 + 보류 레거시 `messages`·`next-question`), DB 마이그레이션 `001`–`011`, 보조금24 수동 동기화 및 검증 시드 4건, 모바일 로그인·프로필·분석 입력·결과·기록 목록 화면, 백엔드 테스트 160개 및 모바일 타입 검사 통과
- **남은 작업**: Home Keeper Supabase에 `011` 적용 여부 확인 및 실기기/실제 로그인 토큰 검증, 요청문·업체 검색·채팅 모바일 화면(WebSocket·읽음 연결), 실제 업체·계정 데이터와 `LLM_API_KEY` 연동 검증, 요청문 생성 시 증상 메모 외부 전송·동의 방식 확정, 소식지 모바일 화면·회원가입·4개 탭, 사진 탐지 기반 진단 생성, 진단 신뢰도 정의 확정

## 문서 안내

| 문서 | 확인할 내용 |
| --- | --- |
| [개발 환경·DB·테스트 가이드](docs/guides/DEVELOPMENT.md) | 상세 디렉토리 구조, 환경변수, 로컬 DB/Supabase·업체 계정 설정, 테스트, 소식지 시드·동기화 |
| [API 사용 가이드](docs/guides/API_USAGE.md) | 공통 오류·버전 규칙, 요청문·업체 검색·채팅 등 `curl` 호출 예시, 레거시 다음 질문 흐름, 구현 메모와 한계 |
| [백엔드 구현 체크리스트](docs/plans/BACKEND_CHECKLIST.md) | 구현된 기능, 남은 MVP 작업과 통합 검증 |
| [MVP 계획](docs/plans/MVP_PLAN.md) | 사용자 흐름, 역할, 시연 범위와 남은 제품 결정 |
| [백엔드 설계](docs/design/BACKEND_DESIGN.md) | 인증, 기록·일괄 분석·소식지·채팅 처리 규칙 |
| [DB 설계](docs/design/DB_DESIGN.md) | 테이블·제약·인덱스와 실제 마이그레이션에서 확정한 내용 |
| [API 설계](docs/design/API_DESIGN.md) | 현재 API 계약과 후속 API 계획, 요청·응답 예시 |
| [용어집](GLOSSARY.md) | 요청인, 업체, 거주 형태, 소식지, 주거 지원 사업, 하자 기록 등의 의미 |
| [프로젝트 계획](docs/plans/PROJECT_PLAN.md) | 제출 요건, 전체 일정, 검증표와 결정 이력 |
| [AI 아이디어 비교](docs/ideas/AI_IDEAS.md) | 후속 기능 후보와 검토 근거 |
| [커밋 규칙](docs/COMMIT_CONVENTION.md) | 커밋 메시지 형식, 타입·스코프 기준과 분리 원칙 |
| [마이그레이션](apps/api/migrations/) | 실제 DB에 적용하는 SQL 마이그레이션 (`001`–`011`) |

## 데이터 출처 및 라이선스

- 주거 지원 사업 소식지 동기화 데이터는 공공데이터포털 [행정안전부_대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do)(보조금24 Open API, 이용허락범위: 제한 없음) 및 확인된 지자체·복지로 공고를 기반으로 합니다. 출처 URL 목록은 [소식지 시드·보조금24 동기화](docs/guides/DEVELOPMENT.md#소식지-시드보조금24-동기화)에서 확인할 수 있습니다.
- 별도 `LICENSE` 파일은 아직 포함되어 있지 않습니다(해커톤 프로젝트).
