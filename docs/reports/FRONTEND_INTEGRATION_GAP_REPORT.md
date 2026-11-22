# 프론트엔드 통합 갭·불일치 보고서

- 대상: `apps/mobile`을 팀원 Home Keeper Expo 앱으로 교체하고 백엔드(`436d690`)와 연동한 작업
- 브랜치: `feat/mobile-team-frontend-integration`
- 기준: 백엔드 실제 코드 `apps/api/app/*.py` (Source of Truth). 문서와 다르면 코드를 따랐습니다.
- 원칙: `apps/api/` 무수정, 기존 문서 무수정, 백엔드에 없는 값은 지어내지 않고 `TODO(integration-gap): GAP-XXX`로 표시
- 경로 표기: 앱 코드는 `apps/mobile/src/` 기준 상대 경로, 백엔드는 `apps/api/app/` 기준

## 0. 반영 현황 (`feat/hyeok-mobile-fixes`, 2026-11-22)

프론트만 고치면 되는 항목을 먼저 반영했습니다. `apps/api`는 수정하지 않았습니다.

| GAP | 반영 내용 | 위치 |
|---|---|---|
| (신규) 사진 업로드 | Expo SDK 58 `expo/fetch`가 `{ uri, name, type }`를 거부("Unsupported FormDataPart implementation")해 네이티브는 `expo-file-system` `File`, 웹은 `Blob`으로 첨부 | `lib/api.ts` `analyzeRecord` |
| GAP-006, GAP-013 | 장소·위치·재질에서 `기타`를 고르면 직접 입력 | `app/(tabs)/analyze/detail.tsx` |
| GAP-007 | 하자 유형을 `균열`·`벗겨짐`·`곰팡이`·`판단 보류`로 정리, 알 수 없는 유형은 판단 보류 | `types.ts`, `services/analyze.ts` |
| GAP-008 | `confidence` 필드와 신뢰도 표시 제거 | `types.ts`, `analyze/result.tsx` |
| GAP-009 | 근접 사진은 요청하지 않은 기능이라 넣지 않음(사진 1장 `overview`만 전송, Hyeok 결정) | `analyze/detail.tsx`, `services/analyze.ts` |
| GAP-011 | 분석 요청마다 외부 AI 사진 전송 동의 체크(기본값은 가입 시 동의 여부). 가입 화면의 필수 동의는 유지 | `analyze/detail.tsx` |
| GAP-014 | 수락 후 빨간 `수락 취소` 버튼으로 되돌리기(Hyeok 결정, `docs/adr/0003`의 수락 확정 규칙을 바꿈). 서버 `POST /quote-requests/{id}/cancel-accept`, 시연용 제안서는 앱 안에서 처리 | `app/dm/index.tsx`, `store/app-store.tsx`, `apps/api/app/quotes.py` |
| GAP-021 | 화면에서 제외(Hyeok 결정). 백엔드 `drafts/provider` API는 그대로 | - |
| GAP-024 | `useRef(...).current`를 `useState` 초기화로 바꿔 린트 오류 0건 | `app/dm/index.tsx` |
| GAP-025 | 권장 대응만 표시. AI 관찰·준비물·확인하지 못한 정보는 화면에서 제외(Hyeok 결정) | `analyze/result.tsx` |
| GAP-029 | `진단 다시 만들기` 버튼(`?regenerate=true`) | `analyze/result.tsx` |
| GAP-030 | 소식지 공고를 펼치면 상세(지원 대상·내용·선정 기준·신청 방법·마감·출처) 표시 | `app/(tabs)/news.tsx` |

### 팀 결정 항목 반영 (Hyeok 확인 또는 기본안)

| GAP | 결정 | 반영 |
|---|---|---|
| GAP-001 | 둘러보기 버튼 유지(대회 규정상 심사위원 체험 경로). Supabase Anonymous sign-ins는 대시보드에서 켬 | 코드 변경 없음 |
| GAP-003 | 가입은 요청인 전용, 업체는 사전 등록 | 가입 화면 회원 유형 선택 제거, 안내 문구 |
| GAP-004 | 가입 지역은 서버 시드 지역(용인)만 | `data/options.ts` `REGIONS` |
| GAP-011 | 가입 화면 동의 제거, 분석 요청마다 동의(기본 미동의) | `app/signup.tsx`, `analyze/detail.tsx` |
| GAP-012 | 법률 검토 전이라 대응 4단계 고정 안내 제거, 집주인 문자는 유지 | `services/analyze.ts` |
| GAP-016, GAP-019 | 요청인 닉네임 비노출, 가입 시 주소 미수집 | 현재 동작 유지 |
| GAP-020 | 팀원 원본 하단 탭 5개(소식·분석·채팅·업체·정보) 유지. 문서의 4탭 안과 다름(Hyeok 결정) | `app/(tabs)/_layout.tsx` |
| GAP-023 | 제안 금액은 원 단위 최소~최대 직접 입력 | `app/dm/index.tsx`, `store/app-store.tsx` |
| GAP-031 | 문서 용어(심각도, 견적 요청서, 업체 제안서) | 화면 문구 전체 |
| 위험도(심각도) 구간 | 서버 기준 40·70 유지 | 현재 동작 유지 |

시연용 가상 데이터(추가): 요청인의 실제 견적 요청서에도 가상 업체 제안서 2건을 앱 안에서 붙입니다(서버 저장 없음, 수락·수락 취소·채팅 모두 앱 안에서 처리). 용인에 실제 업체 계정이 없어 제안서 흐름을 보여 주기 위한 것입니다.

시연용 가상 데이터: 팀원 로컬 앱의 가상 업체 4곳·예시 견적 요청서 3건·업체 제안서 7건과 예시 대화 2개를 `data/demo.ts`로 옮겼습니다(id는 `demo-`로 시작, 지역 용인·유형 3종·금액 원 단위로 맞춤). 서버 데이터 뒤에 함께 보이고, 가상 업체와의 채팅·수락·제안·삭제는 앱 안에서만 처리하며 서버에는 저장하지 않습니다. 서버가 채팅 불가 샘플 업체만 줄 때는 가상 업체로 대신 보여 줍니다. 소식지는 서버에 실제 공고가 있어 예시 소식을 넣지 않았고, 분석 기록 예시는 팀원 로컬 앱에도 없어 넣지 않았습니다.

웹 알림: `react-native-web`의 `Alert.alert`는 브라우저에서 아무것도 띄우지 않아 `lib/alert.ts` `showAlert`(웹은 `window.alert`)로 바꿨습니다.

### 견적 요청서 전달 규칙 변경 (Hyeok 요청)

- 같은 지역(출장 지역)의 업체 계정이면 특화 분야와 관계없이 모든 진행 중 견적 요청서를 받습니다. 목록·상세·제안서 제출 조건에서 작업 종류 일치를 뺐습니다(`apps/api/app/quotes.py`). `docs/adr/0003`의 "지역·특화 분야 기반 1:N" 규칙과 달라져 팀 공유가 필요합니다.
- 새 한국 DB에는 업체 계정이 0개라 실제로 받을 업체가 없습니다. 업체 계정은 가입 화면의 업체 선택(A)으로 결정했습니다(아래 '업체 회원 가입' 참고). 시연용 계정 연결 초안 `docs/drafts/provider-accounts-B-link-demo-vendors.sql`도 남겨 두었습니다(미실행).

### 업체 회원 가입 (GAP-003 결정 변경, Hyeok)

- 가입 화면에 회원 유형(유저/업체)을 되살렸습니다. 업체는 업체명·연락처·소개·활동지역을 입력하고 `POST /me/provider`로 업체 정보(providers)와 활동 지역이 등록되며 프로필 역할이 `provider`가 됩니다.
- 업체 회원의 채팅 두 번째 칸 이름은 `견적서`이며, 활동지역 유저들이 보낸 견적 요청서를 모두 받아 업체 제안서를 보냅니다(일반 유저는 `업체 제안서`).
- 공유 DB에 `apps/api/migrations/018_provider_self_registration.sql`(팀원 브랜치와 동일 내용, 런타임 역할에 providers INSERT/UPDATE, provider_regions·provider_work_types INSERT/DELETE 권한)을 관리자 연결로 적용해야 동작합니다. 적용 전에는 업체 가입 시 `503 provider_registration_unavailable` 안내가 나옵니다. 팀 동의가 필요합니다.

### 웹 데모 실화면 점검 (2026-11-22, 390×844)

| 화면 | 결과 | 조치 |
|---|---|---|
| 로그인·회원가입 | 정상 | - |
| 소식지 목록·상세 | 정상 | - |
| 분석 입력·사진 업로드 | 사진이 서버에 도착(웹 업로드 수정 확인) | - |
| 분석 요청 | `504 llm_timeout`. 설정된 Gemini 모델이 짧은 요청에도 응답하지 않음(설정 문제) | 앱은 서버 안내 문구를 표시. `.env`의 LLM 키·모델 확인 필요 |
| 내 분석 기록·업체 제안서 카드 | 웹에서 `<button>` 안 `<button>` 오류 | 삭제·수락 버튼을 행 버튼 밖으로 분리 |
| 분석 결과 | 임대인 요청문 모델 호출을 기다리느라 20초 넘게 로딩 | 결과 먼저 표시, 요청문은 받은 뒤 채움 |
| 분석 결과·기록 | 서버 유형 `표면 이상`이 `판단 보류`로 표시 | 3종이 아니면 서버 값 그대로 표시 |
| 분석 결과 | 위치가 없을 때 빈 칩·빈 행 | 숨김 |
| 업체·채팅 | 정상(샘플 업체 안내창 표시) | - |
| 내 정보 | `/profile` 주소로 바로 새로고침하면 분석 기록이 안 보임(탭 이동 시 정상) | 미해결, 웹 전용 |

### 백엔드 항목 반영 (Hyeok 동의, `apps/api` 수정, 스키마 변경 없음)

| GAP | 반영 | 위치 |
|---|---|---|
| GAP-002 | `CORSMiddleware` 추가. 허용 주소는 `CORS_ALLOW_ORIGINS`(쉼표 구분), 기본값은 로컬 Expo Web 주소 | `apps/api/app/main.py` |
| GAP-004 | `GET /regions` 인증 없이 조회, 가입 화면이 서버 지역 목록을 씀 | `profile.py`, `app/signup.tsx`, `lib/api.ts` `getPublicRegions` |
| GAP-011 | `external_analysis_consent` 생략 시 `false` | `records.py`, `docs/design/API_DESIGN.md`, `docs/guides/API_USAGE.md` |
| GAP-016 | 견적 요청서에 `requester_nickname` | `quotes.py`, `schemas.py`, `store/app-store.tsx` |
| GAP-017 | 업체 제안서의 업체 정보에 `region_names` | `quotes.py`, `schemas.py`, `store/app-store.tsx` |
| GAP-014 | `POST /quote-requests/{id}/cancel-accept` 추가. 요청서를 `open`으로, 수락 제안서와 그 수락으로 마감된 제안서를 `pending`으로 되돌림. 스키마·권한 변경 없음. `docs/adr/0003`의 "수락은 최종" 규칙과 달라져 팀 공유 필요 | `quotes.py`, `errors.py`, `tests/test_quotes.py` |
| GAP-015 | 보류: 팀 결정 필요. 기록 삭제는 런타임 역할에 `records` DELETE 권한이 없어 공유 DB 마이그레이션이 필요 | 앱은 화면에서만 숨김 |

백엔드 테스트는 단언을 추가·수정했지만 테스트 DB가 없어 실행하지 않았습니다(`test_auth.py`, `test_profile.py`, `test_analyze.py`, `test_quotes.py`, 신규 `test_cors.py`).


## 1. 연동 현황 대시보드

### 1.1 화면·기능별 연동 상태

| 화면·기능 | 파일 | 백엔드 | 상태 |
|---|---|---|---|
| 로그인 | `app/index.tsx` | Supabase `signInWithPassword` | 완료 |
| 회원가입 | `app/signup.tsx` | Supabase `signUp` → `PUT /me/profile` | 부분 연동 (GAP-003, GAP-004, GAP-005) |
| 세션 복원·자동 갱신·로그아웃 | `store/app-store.tsx`, `lib/supabase.ts` | `getSession`, `onAuthStateChange`, `signOut` | 완료 |
| 로그인 없이 둘러보기 | `app/index.tsx` | Supabase `signInAnonymously` | 부분 연동, 설정 필요 (GAP-001) |
| 프로필 등록(404 시) | `app/profile-setup.tsx` (신규) | `GET /me/profile` 404 → `GET /regions` + `PUT /me/profile` | 완료 |
| 프로필 수정 | `app/(tabs)/profile.tsx` | `PUT /me/profile` | 부분 연동 (GAP-003, GAP-010, GAP-019) |
| 역할 분기(유저/업체) | `store/app-store.tsx`, `dm/index.tsx` | `role`, `provider_id` | 어댑터 매핑 완료 |
| 소식지 목록·페이지 | `app/(tabs)/news.tsx`, `services/news.ts` | `GET /support-programs?status=all&limit&offset` | 어댑터 매핑 완료 |
| 소식지 상세 | - | `GET /support-programs/{id}` | 프론트 미구현 (GAP-030, 원문 링크만 연결) |
| 소식지 조건 수정 | `app/(tabs)/news.tsx` | `PUT /me/profile` → 서버 재정렬 | 완료 |
| 사진 선택·촬영 | `app/(tabs)/analyze/index.tsx` | - (기기 로컬) | 완료 (GAP-028) |
| 분석 요청 | `app/(tabs)/analyze/detail.tsx`, `services/analyze.ts` | `POST /records` → `POST /records/{id}/analyze` → `GET /records/{id}` | 부분 연동 (GAP-006, GAP-009, GAP-011, GAP-013) |
| 분석 결과 | `app/(tabs)/analyze/result.tsx` | `GET /records/{id}` (화면 진입마다 새 Signed URL) | 어댑터 매핑 완료 (GAP-007, GAP-008, GAP-025) |
| 판단 보류 | `app/(tabs)/analyze/result.tsx` | `severity_score=null`, `severity_level='undetermined'` | 완료 |
| 진단 재생성 | - | `POST /records/{id}/diagnosis?regenerate=true` | 프론트 미구현 (GAP-029) |
| 집주인 문자(임대인 요청문) | `services/analyze.ts`, `store/app-store.tsx` | `POST /records/{id}/drafts/landlord`, 실패 시 `/template` | 완료 (자가·기타 숨김) |
| 업체 견적 요청문 | - | `POST /records/{id}/drafts/provider` | 프론트 미구현 (GAP-021) |
| 내 분석 기록 | `app/(tabs)/profile.tsx` | `GET /records` | 완료 (삭제는 GAP-015) |
| 업체 목록 | `app/(tabs)/vendors.tsx`, `services/vendors.ts` | `GET /providers?region_id` | 어댑터 매핑 완료 (GAP-018) |
| 분석 결과의 업체 추천 | `app/(tabs)/analyze/result.tsx` | `GET /providers?region_id&work_type_id` | 어댑터 매핑 완료 |
| 업체 상세 | - | `GET /providers/{id}` | 프론트 미구현 (업체 계정 소개 표시에만 사용) |
| 작업 종류 목록 | - | `GET /work-types` | 프론트 미구현 (추천 작업은 진단값 사용) |
| 견적서 보내기 | `app/(tabs)/analyze/result.tsx` | `POST /quote-requests` | 완료 |
| 견적서·제안서 목록 | `app/dm/index.tsx` | `GET /quote-requests`, `GET /quote-requests/{id}` | 어댑터 매핑 완료 (GAP-016, GAP-017) |
| 제안서 보내기(업체) | `app/dm/index.tsx` | `POST /quote-requests/{id}/proposals` | 어댑터 매핑 완료 (GAP-023) |
| 제안서 수락 | `app/dm/index.tsx` | `POST .../proposals/{id}/accept` | 완료 |
| 수락 취소 | `app/dm/index.tsx` | 없음 | 백엔드 미구현 (GAP-014) |
| 견적서 취소 | `app/dm/index.tsx` 삭제 버튼 | `POST /quote-requests/{id}/cancel` | 완료 (진행 중인 내 요청서만) |
| 채팅 목록 | `app/dm/index.tsx` | `GET /chat/rooms` (`unread_count`) | 완료 |
| 채팅방 열기 | `app/dm/[vendorId].tsx` | `POST /chat/rooms` (`record_id` 공유) | 완료 |
| 메시지 이력·전송·읽음 | `app/dm/[vendorId].tsx`, `store/app-store.tsx` | `GET/POST /chat/rooms/{id}/messages`, `POST .../read` | 완료 (`client_message_id` UUID) |
| 실시간 수신 | `store/app-store.tsx` | `WS /chat/ws` + 재연결 후 REST 동기화 | 완료 (GAP-026) |
| 공통 오류 처리 | `lib/api.ts`, `store/app-store.tsx` | 401/404/409/422/502/503/504 | 완료 (아래 5.1 참고) |

### 1.2 남아 있는 Mock·하드코딩 데이터 전수 목록

| 파일 | 심볼 | 남겨 둔 이유 | GAP |
|---|---|---|---|
| `data/options.ts:4` | `REGIONS` | 가입 화면은 로그인 전이라 `GET /regions`(인증 필요)를 부를 수 없음. 로그인 후 화면은 서버 목록 사용 | GAP-004 |
| `data/options.ts:19` | `LOCATIONS` | 장소 선택지(UI 입력값). 백엔드는 자유 입력 문자열이라 충돌 없음 | GAP-013 |
| `data/options.ts:22` | `MATERIALS` | 백엔드 필수값 `material`을 받기 위해 추가한 선택지 | GAP-006 |
| `data/options.ts:25` | `POSITIONS` | 위치 선택지(UI 입력값). `location`에 합쳐 전송 | GAP-013 |
| `services/analyze.ts:97` | `buildGuide().steps` | 세입자 대응 순서 4단계 하드코딩. 백엔드 API 없음 | GAP-012 |
| `services/analyze.ts:106` | `buildGuide().message` 기본 문구 | 임대인 요청문 API와 template이 모두 실패했을 때만 쓰는 대체 문구 | GAP-012 |
| `services/analyze.ts:9` | `ANALYSIS_STEPS` | 진행 단계 표시 문구. 서버는 단일 요청이라 실제 단계와 1:1이 아님 | - |
| `app/dm/index.tsx:14` | `PRICES` | 제안 가격 선택지 5~10만원 고정 | GAP-023 |
| `services/vendors.ts:13` | `phone ?? '연락처 없음'` | 서버 `phone=null` 표시용 문구 | GAP-018 |
| `store/app-store.tsx:317` | `userNickname: '요청인'` | 업체에게 요청인 닉네임을 주지 않음 | GAP-016 |
| `store/app-store.tsx:340` | `vendorRegion: ''` | 제안서 업체 정보에 지역 없음 | GAP-017 |

삭제한 mock: `data/vendors.ts`(가상 업체 A~D), `data/samples.ts`(예시 견적서·제안서), `data/news.ts`(예시 소식지), `store/app-store.tsx`의 in-memory 계정·게스트 계정·가상 업체 자동 응답, `services/analyze.ts`의 장소별 고정 결과(`MOCK`, `LOW_CONFIDENCE`).

## 2. Blocker · 인프라 · 인증 · 보안 이슈

1. **로그인 없이 둘러보기 (GAP-001, Blocker)**: 백엔드 모든 데이터 API가 인증을 요구합니다(`auth.py:84` `get_current_user`). 대회 규정상 심사위원 체험 경로가 필요하므로 Supabase 익명 로그인(`store/app-store.tsx:488`)으로 연결했습니다. Supabase 대시보드에서 Anonymous sign-ins를 켜지 않으면 "둘러보기가 서버에서 꺼져 있습니다" 안내만 뜹니다. 익명 사용자는 프로필 등록 화면을 거치며, 외부 AI 분석 동의는 `false`로 보냅니다(`store/app-store.tsx:434`). 단 `docs/plans/PROJECT_PLAN.md:66,78`은 "비회원 열람은 검토 중이며 익명 계정이 필요 없다"고 적고 있어 방향이 다릅니다. 팀 결정이 필요합니다.
2. **Expo Web CORS 부재 (GAP-002, High)**: `main.py`에 `CORSMiddleware`가 없습니다. iOS·Android(Expo Go, 시뮬레이터)는 영향이 없지만 `npm run web`으로 브라우저에서 API를 부르면 모두 실패합니다. 백엔드에 허용 Origin 설정을 추가해야 합니다(이번 작업에서는 수정하지 않음).
3. **Supabase 이메일 확인 설정 (GAP-005, High)**: 팀원 UI의 ID를 Supabase Auth 이메일로 매핑했습니다. 프로젝트에서 Confirm email이 켜져 있으면 `signUp`이 세션을 주지 않아 가입 직후 프로필 저장을 못 하고 "인증 메일을 확인해 주세요"로 끝납니다. 시연 전 설정 확인이 필요합니다. 비밀번호 최소 길이도 팀원 UI 4자 → Supabase 기본 6자로 바꿨습니다(`app/signup.tsx`).
4. **WebSocket 토큰 전달 (GAP-026, Low)**: 네이티브는 `Authorization` 헤더, 웹은 브라우저가 헤더를 못 붙여 `?access_token=` 쿼리를 씁니다(`store/app-store.tsx:378`, 백엔드 `chat.py:627`이 둘 다 지원). 쿼리 토큰은 프록시 로그에 남을 수 있어 운영 시 주의가 필요합니다.
5. **하드코딩 키·시크릿 점검**: 팀원 코드 전체에서 API 키, Supabase `service_role` 키, 토큰, 비밀번호 하드코딩은 발견되지 않았습니다. 팀원 앱의 비밀번호는 in-memory 비교였고 이번에 Supabase Auth로 교체했습니다. 환경변수는 기존 `apps/mobile/.env.example`의 `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`를 그대로 씁니다.
6. **Expo SDK·의존성**: 팀원 앱과 기존 앱 모두 Expo SDK 58, React Native 0.88.1, Expo Router라 충돌이 없었습니다. 병합 결과는 팀원 의존성 + `@supabase/supabase-js`, `expo-sqlite`(세션 저장)입니다. 팀원 앱의 `@expo/ngrok`은 개발 도구라 뺐습니다. `app.json`에 `expo-sqlite` 플러그인과 사진·카메라 권한 문구를 넣었습니다. `@expo/ui`, `expo-glass-effect`, `expo-symbols` 등은 현재 코드에서 쓰지 않지만 팀원 설정을 유지했습니다.
7. **린트 (GAP-024, Low)**: `npx expo lint`에서 팀원 원본 코드 `app/dm/index.tsx:233`(`useRef(new Animated.Value(...)).current`)가 React Compiler 규칙 `react-hooks/refs` 오류 4건을 냅니다. 동작에는 문제가 없고 팀원 UI 코드라 수정하지 않았습니다. 이번에 추가한 코드의 린트 오류는 0건입니다.

## 3. 백엔드에 부족하거나 추가가 필요한 항목

| GAP | 팀원 프론트가 요구하는 것 | 현재 백엔드 |
|---|---|---|
| GAP-001 | 비회원 열람 | 모든 API 인증 필수 |
| GAP-003 | 가입 시 업체 회원 유형 선택, 프로필에서 회원 유형 변경 | 가입은 항상 `requester`, 역할 변경 불가 (`profile.py:107`) |
| GAP-004 | 가입 화면에서 지역 목록 | `GET /regions` 인증 필수 (`profile.py:182`), 시드는 `경기도`, `경기도 용인시`뿐 |
| GAP-008 | AI 신뢰도(%) 표시 | `DiagnosisOut`(`schemas.py:269`)에 confidence 없음 |
| GAP-010 | 업체 소개 수정 | 업체 정보 수정 API 없음 |
| GAP-014 | 제안서 수락 취소 | 수락 취소 API 없음 (수락은 최종) |
| GAP-015 | 분석 기록·견적서·제안서 삭제 | 기록 삭제, 제안서 삭제·철회 API 없음 (요청서는 `cancel`만) |
| GAP-016 | 업체가 받은 견적서에 요청인 닉네임 | `QuoteRequestSummary`(`schemas.py:515`)에 요청인 정보 없음 |
| GAP-017 | 제안서에 업체 지역 | `ProviderOut`(`schemas.py:800`)에 지역 없음 |
| GAP-007 | `누수`, `결로` 하자 유형 | 진단 유형은 `균열`, `벗겨짐`, `곰팡이`뿐 (`diagnosis.py:46`) |

## 4. 프론트엔드에 부족하거나 수정이 필요한 항목

| GAP | 백엔드 계약 | 팀원 UI 상태 | 이번 조치 |
|---|---|---|---|
| GAP-006 | `analyze`의 `material` 필수 | 재질 입력 없음 | `analyze/detail.tsx`에 팀원 `Select`로 재질 칸 추가. 디자인 확인 필요 |
| GAP-009 | 사진 1~2장(`overview`/`closeup`) | 사진 1장 | 1장을 `overview`로 전송. 근접 사진 선택 UI는 미구현 |
| GAP-011 | 분석 요청마다 `external_analysis_consent` (생략 시 `true`, `records.py:711`) | 가입 화면 체크박스 1회(`app/signup.tsx:129`), 서버에 동의 기록 없음 | 가입 계정은 `true`, 익명은 `false`로 명시 전송. 로그인만 한 기존 계정도 `true`로 간주하므로 분석 화면 동의 UI 검토 필요 |
| GAP-019 | 프로필 `address`(선택) | 주소 입력 없음 | 기존 값 유지, 새 가입은 `null` |
| GAP-021 | `POST /records/{id}/drafts/provider` 견적 요청문 | 요청문 복사 UI 없음 | 미구현. 채팅방 생성 시 서버가 기록 요약 메시지를 자동 공유 |
| GAP-025 | `unknowns`, `supplies`, `recommended_action`, `observations`, 사진 관찰 결과 | 원인·해결·재발방지 3섹션만 | `estimation_notice`는 위험도 카드에 표시, 판단 보류 시 `unknowns`를 원인 칸에 표시. 나머지는 미표시 |
| GAP-028 | 사진은 서버 비공개 Storage에 저장 | 사진 목록은 기기 메모리(새로고침 시 초기화) | 분석 후 결과·기록 사진은 서버 Signed URL 사용 |
| GAP-029 | 진단 재생성 `?regenerate=true`, `409 revision_conflict` | 재생성 버튼 없음 | 미구현. 분석 409는 오류 메시지로 표시 |
| GAP-030 | 소식지 상세 API | 목록 펼치기만 있음 | 펼치면 `detail_url` 원문 링크 표시 |
| GAP-012 | (해당 API 없음) | 세입자 대응 순서 하드코딩 | 유지, 보고 |

## 5. 프론트–백엔드 스키마·계약 상충 항목

### 5.1 어댑터로 매핑 완료

| 항목 | 백엔드 | 팀원 프론트 | 매핑 위치 |
|---|---|---|---|
| 거주 형태 | `monthly_rent`, `jeonse`, `semi_jeonse`, `owned`, `other` | `월세`, `전세`, `자가`, `기타` (반전세 없음) | `lib/adapters.ts` (반전세 선택지 추가) |
| 회원 유형 | `requester`, `provider` | `유저`, `업체` | `lib/adapters.ts` |
| 지역 | `region_id` UUID + `display_name` | 지역 이름 문자열 | `lib/adapters.ts`, 화면 선택지는 `GET /regions` |
| 로그인 ID | 이메일 | 자유 ID | 이메일 형식 검사 후 그대로 사용 |
| 장소 + 위치 | `location` 문자열 1개 | `장소`, `위치` 2개 | `services/analyze.ts:18` `'화장실 · 벽면'`으로 합치고 결과에서 다시 나눔 (GAP-013) |
| 메모 | `symptoms` | `memo` | `services/analyze.ts` |
| 위험도 | `severity_score` 0~100 또는 `null` | `risk` 0~100 | `null`은 `판단 보류`로 표시 |
| 위험도 구간 | `<40 low`, `<70 medium`, `≥70 high` (`diagnosis.py:203`) | `<60 낮음`, `<80 주의`, `≥80 높음` | `constants/theme.ts:52`, 범례를 백엔드 기준으로 변경 |
| 원인·해결·재발방지 | `causes`+`reason`, `care_steps`, `prevention_tips` | `cause`, `solutions`, `prevention` | `services/analyze.ts` `toAnalysisResult` |
| 견적서 | `quote-request` (`status`, `accepted_proposal_id`) | `Estimate` | `store/app-store.tsx` `refreshQuotes` |
| 제안 가격 | `min_price`, `max_price` (원) | `price` (만원, 단일값) | ×10000 전송, 범위면 `5~7만원` 표시 |
| 채팅 | 방(`room_id`) 단위, `sender_id` | 업체(`vendorId`) 단위 | 방 목록은 `GET /chat/rooms`, 화면 파라미터에 `roomId` 추가 |
| 업체 별점 | `rating`, `review_count`, 별점순 정렬 | 표시 없음 | 업체 목록에 별점 한 줄 추가 |
| 샘플 업체 | `is_sample`, `chat_available=false` | 가상 업체 고정 안내 | 샘플일 때만 안내, 채팅 불가 업체는 전화 안내 |
| 소식지 | `items, total, has_more`, 서버 정렬 | 로컬 정렬·페이지 | `services/news.ts`, 페이지 수는 `total` 기준 |
| 공통 오류 | `{code, message}` | 문자열 오류 | `lib/api.ts` `ApiError`. 프로필 조회 401은 로그아웃 후 재로그인 안내, 그 밖의 401은 서버 메시지 표시, 프로필 404는 등록 화면, 409 코드별 문구(`request_already_open`, `diagnosis_required`, `request_not_open`, `proposal_already_exists`), 초안 502/503/504는 template 폴백 |

### 5.2 미해결 상충

| GAP | 항목 | 백엔드 | 팀원 프론트 |
|---|---|---|---|
| GAP-007 | 하자 유형 | `균열`, `벗겨짐`, `곰팡이` | `곰팡이`, `균열`, `누수`, `결로`, `판단 보류` (`벗겨짐` 없음). 타입에 `벗겨짐`만 추가 |
| GAP-008 | 신뢰도 | 없음 | 재촬영 기준(신뢰도 0.6)과 표시. 판단 보류로 대체 |
| GAP-013 | 위치 입력 | 자유 입력 문자열 | 선택지만 있음 (직접 입력 불가) |
| GAP-023 | 제안 가격 | 원 단위 범위, 상한 없음 | 5~10만원 6개 선택지 |
| GAP-018 | 업체 전화 | `null` 가능 | 필수 문자열 |

## 6. 레포 문서와 팀원 프론트 간 기획·소통 차이

| 주제 | 레포 문서 | 팀원 프론트 | 비고 |
|---|---|---|---|
| 소셜 로그인 | 카카오·Google 후순위, MVP 제외 (`PROJECT_PLAN.md:64`) | 없음 | 일치 |
| 로그인 없이 둘러보기 | 검토 중, 비회원은 전체 소식·업체만, 익명 계정 불필요 (`PROJECT_PLAN.md:66,78`) | 버튼 있음, 모든 화면 진입 | GAP-001. 이번엔 익명 로그인으로 연결 |
| 회원 유형 | 일반 가입은 요청인 전용, 업체는 사전 등록 (`PROJECT_PLAN.md:87`) | 가입 시 유저/업체 선택, 프로필에서 변경 | GAP-003 |
| 가입 항목 | 닉네임·이메일·PW·거주 지역·등록 주소(선택)·거주 형태 5종 (`PROJECT_PLAN.md:87`) | 등록 주소 없음, 반전세 없음 | GAP-019, 반전세는 추가 |
| 개인정보·외부 AI 동의 위치 | 분석 호출 전에 사진·제공사·목적을 안내하고 동의 (`PROJECT_PLAN.md:182`) | 가입 화면 1회 동의 | GAP-011 |
| 프로필 사진 | 제외 확정 (`PROJECT_PLAN.md:74`) | `avatarUri` 타입만 있고 UI 없음 | 일치 |
| 하단 탭 | 4개: 소식지·분석·채팅·내 정보 (`PROJECT_PLAN.md:23`) | 5개: 소식·분석·채팅·업체·정보 | GAP-020 |
| 용어: 하자 유형 | `균열`, `벗겨짐`, `곰팡이`, Avoid: 크랙·박리 (`GLOSSARY.md:27-28`) | `균열` 사용, `누수`·`결로` 추가, `벗겨짐` 없음 | GAP-007 |
| 용어: 위험도 | `심각도` (`GLOSSARY.md:24,34`) | `AI 위험도`, `위험도` | GAP-031 |
| 용어: 장소·위치 | 집 안 `위치` 1개 (`GLOSSARY.md:18,21`은 거주 지역과 구분) | `장소`(방 이름) + `위치`(벽면 등) 2개 | GAP-013 |
| 용어: 견적 | `견적 요청서`, `업체 제안서` (`GLOSSARY.md:48,52`) | `견적서`, `제안서` | GAP-031 |
| 분석 입력 | 사진 1~2장 + 위치(선택+직접 입력) + 재질(선택+직접 입력) + 증상 (`PROJECT_PLAN.md:92`) | 사진 1장 + 장소·위치 선택 + 메모 | GAP-006, GAP-009, GAP-013 |
| 위험도 구간 | 시안 60·80 vs 샘플 40·70, 회의에서 결정 (`PROJECT_PLAN.md:83`) | 60·80 | 앱을 서버 기준 40·70으로 맞춤. 팀 확정 필요 |
| 시연 지역 | 용인 (`PROJECT_PLAN.md:91`) | 서울 등 10개 지역 | GAP-004 |
| 세입자 처리 요령 | 임대인 점검 요청문(LLM, 실패 시 기본 양식), 자가 예외 (`PROJECT_PLAN.md:107,161`) | 대응 순서 4단계 하드코딩 + 문자 예시 | 문자는 API 연결, 순서는 GAP-012 |
| 결과 화면 | 의심 영역 표시, 산정 근거, AI 추정 안내, 미확인 정보 (`PROJECT_PLAN.md:94`) | 의심 영역 원 미표시, 신뢰도 표시 | GAP-008, GAP-025 |
| 업체 평점·리뷰 | 별점순 정렬 (`providers.py`), 리뷰 작성 기능 없음 | 평점 표시 없음, 리뷰 없음 | 별점 표시만 추가 |
| 업체 매칭 방식 | 1:N 공개 견적 요청서 + 제안 + 수락 1건 (`adr/0003`) | 주변 업체에 한 번에 전송, 수락 취소 가능 | 공개 방식은 일치, 수락 취소는 GAP-014 |
| 업체 채팅 | 1:1 채팅, 하자 요약 자동 공유, 샘플 업체는 시연 안내 (`PROJECT_PLAN.md:100`) | 가상 업체 자동 응답 | API 연결 완료 |
| 요청문 복사 | 업체 목록에서 견적 초안 복사 (`PROJECT_PLAN.md:107`) | 없음 | GAP-021 |

## 7. 팀 의사결정용 통합 이슈 표

| ID | 심각도 | 분류 | 백엔드 실제 코드 | 팀원 프론트 기대 | 레포 문서 | 추천 해결 방향 |
|---|---|---|---|---|---|---|
| GAP-001 | Blocker | 인증 | 모든 API 인증 필수 (`auth.py:84`) | 로그인 없이 둘러보기 (`app/index.tsx:106`) | 검토 중, 익명 계정 불필요 (`PROJECT_PLAN.md:66,78`) | 단기: Supabase 익명 로그인 허용(현재 구현). 중기: 소식·업체 조회만 공개 API로 열기(백엔드 수정) |
| GAP-002 | High | 인프라 | CORS 없음 (`main.py`) | Expo Web 실행 가능 | 언급 없음 | 백엔드 수정: 허용 Origin 설정. 시연은 네이티브로 |
| GAP-003 | High | 역할 | 가입은 항상 `requester` (`profile.py:107`) | 가입·프로필에서 업체 선택 | 업체는 사전 등록 (`PROJECT_PLAN.md:87`) | 프론트 수정: 가입 화면 회원 유형 선택 제거 또는 안내로 변경 (현재 업체 선택 시 안내 후 차단) |
| GAP-004 | High | 지역 | `/regions` 인증 필수, 시드 용인·경기도뿐 | 가입 화면 10개 지역 | 시연 지역 용인 | 백엔드: `/regions` 공개 또는 지역 시드 추가. 프론트: 가입 지역 선택지를 용인으로 축소 |
| GAP-005 | High | 인증 | Supabase 이메일·비밀번호 | 자유 ID, PW 4자 | 이메일·PW (`PROJECT_PLAN.md:87`) | 프론트 수정 완료(이메일, 6자). Supabase Confirm email 설정 확인 |
| GAP-006 | High | 분석 입력 | `material` 필수 (`records.py`) | 재질 입력 없음 | 재질 선택+직접 입력 | 프론트: 재질 칸 추가함. 팀원 디자인 확인과 직접 입력 지원 |
| GAP-007 | Medium | 용어·도메인 | 유형 `균열`, `벗겨짐`, `곰팡이` | `누수`, `결로` 포함, `벗겨짐` 없음 | GLOSSARY 3종 확정 | 프론트 수정: 유형 라벨을 3종으로 정리 |
| GAP-008 | Medium | 결과 | confidence 없음, 판단 보류로 표현 | 신뢰도 %·재촬영 기준 | 판단 보류·미확인 정보 | 프론트 수정: 신뢰도 표시 제거(현재 null이면 숨김) |
| GAP-009 | Medium | 분석 입력 | 사진 1~2장 + 역할 | 1장 | 1~2장 | 프론트: 근접 사진 선택 추가 |
| GAP-010 | Low | 업체 | 업체 정보 수정 API 없음 | 업체 소개 수정 | 업체 사전 등록 | 프론트: 표시 전용 유지(현재) |
| GAP-011 | High | 개인정보 | 요청별 동의, 생략 시 `true` | 가입 1회 동의 | 분석 호출 전 안내·동의 | 프론트: 분석 화면에 동의 체크 추가 권장. 백엔드: 생략 기본값 `false` 검토 |
| GAP-012 | Medium | 하드코딩 | 대응 순서 API 없음 | 세입자 4단계 하드코딩 | 요청문 중심 | 팀 결정: 정적 안내 유지 여부, 문구 법률 검토 |
| GAP-013 | Low | 스키마 | `location` 1개 자유 입력 | 장소·위치 2개 선택 | 위치 선택+직접 입력 | 어댑터로 합침(현재). 직접 입력은 프론트 추가 |
| GAP-014 | Medium | 상태 흐름 | 수락 취소 API 없음 | 수락 취소 버튼 | 수락 1건 확정 (`adr/0003`) | 프론트 수정: 버튼 제거 (현재 누르면 미지원 안내) |
| GAP-015 | Low | 삭제 | 기록·제안서 삭제 API 없음 | 삭제 버튼 | 보유·삭제 정책 미정 | 현재 내 화면에서만 숨김. 정책 확정 후 백엔드 추가 |
| GAP-016 | Low | 스키마 | 요청서에 요청인 정보 없음 | 업체 화면에 요청인 닉네임 | 경쟁 제안 비노출만 명시 | 팀 결정: 닉네임 노출 여부. 노출 시 백엔드 필드 추가 |
| GAP-017 | Low | 스키마 | 제안서 업체 정보에 지역 없음 | 업체 지역 표시 | - | 백엔드: `ProviderOut`에 지역 추가 또는 프론트에서 제거 |
| GAP-018 | Low | 스키마 | `phone` null 가능 | 필수 | 샘플 업체 연락처 없음 | 어댑터 처리 완료 |
| GAP-019 | Low | 프로필 | `address` 선택 | 주소 입력 없음 | 선택 입력 유지, 논의 중 | 팀 결정: 주소 수집 여부 |
| GAP-020 | Low | 기획 | - | 탭 5개(업체 탭 포함) | 탭 4개 | 팀 결정 |
| GAP-021 | Medium | 기능 | 업체 견적 요청문 API 있음 | UI 없음 | 업체 목록에서 초안 복사 | 프론트 추가 |
| GAP-023 | Low | 스키마 | 원 단위 범위 | 만원 6개 선택 | 업체 입력값만 저장 | 팀 결정: 가격 입력 방식 |
| GAP-024 | Low | 린트 | - | `dm/index.tsx:233` 렌더 중 ref 접근 | - | 프론트: `useRef` 대신 `useState(() => new Animated.Value())` |
| GAP-025 | Medium | 결과 | `unknowns`, `supplies`, 사진 관찰 결과 | 3섹션만 | 미확인 정보·의심 영역 표시 | 프론트 추가 |
| GAP-026 | Low | 보안 | WS 토큰 헤더/쿼리 모두 허용 | 웹은 쿼리 | - | 운영 시 웹 쿼리 토큰 재검토 |
| GAP-028 | Low | 사진 | 서버 Storage | 분석 전 사진은 메모리 | 로컬·서버 보관 미정 | 현재 유지 |
| GAP-029 | Low | 기능 | 진단 재생성 API | 없음 | 실패 시 다시 시도 | 프론트 추가 |
| GAP-030 | Low | 기능 | 소식지 상세 API | 펼치기만 | 목록·상세 | 프론트 추가 |
| GAP-031 | Low | 용어 | `심각도`, `견적 요청서`, `업체 제안서` | `위험도`, `견적서`, `제안서` | GLOSSARY | 팀 결정: 화면 용어 통일 |

## 부록: 검증 결과

- `git diff 436d690 -- apps/api`: 변경 0줄
- `npm run typecheck --workspace @career-pair/mobile`: 통과
- `npx expo lint` (apps/mobile): 오류 4건, 모두 팀원 원본 `app/dm/index.tsx:233` (GAP-024). `feat/hyeok-mobile-fixes`에서 0건으로 수정
- 실제 기기·시뮬레이터 실행과 백엔드 연결 테스트는 하지 않았습니다(Supabase·API 환경 없음). 시연 전 실기기 확인이 필요합니다.
