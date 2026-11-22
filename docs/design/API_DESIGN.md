# MVP API 계약 초안

[백엔드 설계](BACKEND_DESIGN.md)와 [DB 설계](DB_DESIGN.md)의 합의를 요청·응답으로 구체화한 초안이다. 경로·필드명은 앱 담당자와 최종 확인할 대상이다. 아래 UUID 값은 문서에서 읽기 쉽도록 자리표시자로 적었다.

## 문서 범위

현재 코드에 구현된 API는 기록 생성·조회·수정(`POST /records`, `GET /records/{record_id}`, `PATCH /records/{record_id}`), 내 기록 목록(`GET /records`), 사진·위치·재질 일괄 분석(`POST /records/{record_id}/analyze`), 구조화 진단 생성·재생성(`POST /records/{record_id}/diagnosis`), 프로필(`GET/PUT /me/profile`), 지역 목록(`GET /regions`), 주거 지원 사업 소식지(`GET /support-programs`, `GET /support-programs/{program_id}`), 요청문 생성·기본 양식(`POST /records/{record_id}/drafts/{kind}`, `GET /records/{record_id}/drafts/{kind}/template`), 작업 종류·업체 검색·상세(`GET /work-types`, `GET /providers`, `GET /providers/{provider_id}`), 견적 요청서·제안서(`POST/GET /quote-requests`, `GET /quote-requests/{request_id}`, `POST .../proposals`, `.../accept`, `.../cancel`), 1:1 채팅(`GET/POST /chat/rooms`, `GET/POST /chat/rooms/{room_id}/messages`, `POST /chat/rooms/{room_id}/read`, WebSocket `/chat/ws`)이다. 이미 구현된 `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`은 분석 채팅창 제거에 따라 **현재 MVP 미사용(보류/레거시)** 상태이며, 문서 하단에 참고용으로 분리했다.

사진 관찰과 텍스트 진단은 2단계로 구현했다. 실시간 채팅은 WebSocket과 방별 미읽음 수 표시로 백엔드에 구현했다. 진단 신뢰도 필드는 정의가 정해지지 않아 구현하지 않았다. 요청문 생성은 서버에서 Google Gemini API를 사용한다. 실행 절차는 [개발 환경·DB·테스트 가이드](../guides/DEVELOPMENT.md), 호출 예시와 구현 메모는 [API 사용 가이드](../guides/API_USAGE.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `POST /records`는 201과 `record_id`, `input_revision`(최초 0)을 반환한다.
- `GET /records/{record_id}`는 저장된 입력(`location`, `material`, `symptoms`, `region_id`, `region_name`, `photo_observations`, `photos`)과 `diagnosis`, `drafts`의 생성 당시 버전 및 `is_current`를 반환한다. *(구현본에는 레거시 `questions`, `messages`, `next_question` 필드도 함께 포함된다.)*
- `PATCH /records/{record_id}`는 `location`·`material`·`symptoms`·`region_id`를 받고 `input_revision`을 요구하지 않는다. 실제 값이 바뀔 때만 버전을 올리며, 명시한 `null`은 값을 지운다. `region_id`는 `regions`에 존재해야 한다.
- `POST /records/{record_id}/analyze`는 사진 1~2장과 위치·재질·증상·분석 지역·외부 분석 동의(기본 `true`)를 multipart로 받아 사진 관찰과 구조화 진단을 저장한다. `region_id`를 생략하면 기존 기록 또는 프로필 거주 지역을 스냅샷으로 저장한다. 두 모델 경로가 모두 미설정이면 샘플 모드다. 자세한 계약은 아래 일괄 분석 섹션을 따른다.
- `POST /records/{record_id}/diagnosis`는 `regenerate=false`이고 진단 입력 버전이 현재 입력과 같으면 모델을 호출하지 않고 기존 진단을 반환한다. 재생성은 `regenerate=true`이며 실패 시 기존 진단을 유지한다.
- 공통 오류 형식은 `{ "code", "message", "input_revision"? }`이다. 처리하지 못한 서버·DB 오류는 내용을 노출하지 않고 500 `internal_error`로 반환한다.
- 요청문은 `input_revision`과 `diagnosis_generation`이 모두 같은 저장본만 재사용하고, `regenerate=true`일 때만 모델을 다시 호출한다. 실패 시 기존 저장본과 기본 양식을 유지한다.
- 채팅방은 `(requester_id, provider_id)` 유일 제약으로 하나만 존재하고, 메시지는 `(room_id, client_message_id)` 유일 제약으로 재전송을 멱등 처리한다. 메시지 목록은 `created_at`, `id` 오름차순이며 `limit`·`offset` 페이지를 사용한다.
- *(MVP 미사용/보류)* `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`의 구현 확정 사항은 문서 하단 레거시 섹션에 유지한다.

## 11월 21일 결정 사항과 현재 API의 구분

- **확정**: 이메일·비밀번호 인증, 프로필 사진 제외. 카카오·Google 로그인은 현재 MVP에서 제외하고 시간 여유 시 재검토한다.
- **확정·백엔드 구현 완료**: WebSocket 실시간 채팅과 채팅방 목록의 방별 미읽음 수. 경로는 `/chat/ws`, 이벤트는 `ready`·`message`, 읽음은 `POST /chat/rooms/{room_id}/read`다. 읽음 시점은 앱이 방에 들어가 메시지 이력을 받은 직후로 정했다. 서버가 시각을 저장하므로 같은 계정의 다른 기기도 같은 읽음 상태를 쓴다. 상세 계약은 [채팅 섹션](#업체요청인-11-채팅-chat-구현-완료)을 따른다.
- **확정·미구현(정의 대기)**: 진단 신뢰도 필드. 무엇의 신뢰도인지, 산정 방법·필드명·범위·산정 불가 표현이 정해지지 않아 스키마·산정·UI를 추가하지 않았다. YOLO 개별 탐지 `confidence`를 진단 전체 신뢰도로 사용하지 않는다.
- **미정**: 비회원 전체 소식·업체 열람안, “분석을 해야 등록되는 흐름”의 대상·시점, 발생/발견일 입력, 사진 보관, 가상 업체 문의·자동 응답. 분석·기록·프로필·채팅의 인증은 유지한다. 미정 항목 때문에 현재 인증·입력·샘플 업체 계약을 바꾸지 않는다.
- 세부 근거·선택지는 [프로젝트 계획의 시안 검토](../plans/PROJECT_PLAN.md#11월-21일-프론트-시안-검토)를 따른다. 이번 변경은 채팅 백엔드에 한정하며 모바일 채팅 화면과 회원가입 화면은 포함하지 않는다.

## 회원가입과 프로필 (프로필 API 구현 완료)

일반 회원가입은 `요청인` 전용이다. 앱에서 Supabase Auth로 **이메일·비밀번호** 계정을 만들고, 회원가입 과정에서 `닉네임`, `거주 지역`(필수), `등록 주소`(선택), `거주 형태`(`월세`, `전세`, `반전세`, `자가`, `기타`)를 입력받는다. 인증 가능한 세션을 얻은 뒤 FastAPI에 프로필을 저장한다. 이메일 확인이 필요한 환경은 확인 후 동일 계정으로 프로필 등록을 완료한다. 계정 생성 후 프로필 저장에 실패하면 프로필 저장만 재시도한다. 시연용 `업체` 계정은 Supabase Auth와 `profiles`(`role="provider"`)에 사전 등록한다.

백엔드는 별도 회원가입 API를 추가하지 않는다. 계정 생성·이메일 확인은 Supabase Auth가 담당하고, FastAPI는 로그인 후 발급된 JWT와 `PUT /me/profile` upsert를 재사용한다. 앱은 `signUp` 응답에 세션이 없으면(이메일 확인 필요) 확인 안내를 표시하고, 확인 후 로그인해 프로필 저장을 이어간다. 프로필 저장 실패 시 같은 사용자로 `PUT /me/profile`을 다시 호출하면 한 행만 유지된다.

| API | 동작 |
| --- | --- |
| `GET /me/profile` | 인증된 본인의 `nickname`, `role`, `region_id`, `address`, `housing_type`을 조회한다. 미등록이면 `404`(`not_found`)를 반환해 앱이 등록 화면으로 이어간다. |
| `PUT /me/profile` | `nickname`, `region_id`, `address`(선택/null 가능), `housing_type`을 받아 인증된 본인의 프로필을 등록·수정한다. `user_id`는 토큰에서 결정하고 `role`은 요청에서 받지 않는다. |

구현 확정 사항:
- `PUT /me/profile`은 `(user_id)` 기준 upsert다. 같은 사용자로 다시 호출하면 한 행을 수정하며, 저장 실패 후 같은 계정으로 재시도해도 중복 프로필이 생기지 않는다.
- 새 프로필의 `role`은 서버가 `requester`로 정한다. 요청에 `role` 또는 `user_id`가 있으면 추가 필드로 거부하며(`422`), 기존 업체 계정의 `provider` 역할은 일반 프로필 저장으로 바뀌지 않는다.
- `nickname`은 앞뒤 공백을 제거하고, 공백만 입력하면 `422`다. `address`는 앞뒤 공백을 제거하고 빈 문자열이면 `null`로 저장한다.
- `region_id`는 `GET /regions`에 있는 지역 UUID여야 하며, 없으면 `422`다. `housing_type` 허용값은 `monthly_rent`(월세), `jeonse`(전세), `semi_jeonse`(반전세), `owned`(자가), `other`(기타)다.

주소·지역이 필요한 화면(임대인 점검 요청, 업체 찾기)에서 앱은 등록 주소와 거주 지역을 보여주고 맞는지 확인한다. 다르면 위 프로필 저장 API로 수정한 뒤 사용한다. 프로필 미등록 상태에서도 기존 계정의 로그인과 기록 조회는 가능하며, 프로필이 필요한 행동에서 등록을 안내한다.

소식지 API는 서버가 로그인 사용자의 프로필 거주 지역 ID를 사용하고, 업체 검색은 앱이 확인한 `region_id`를 보낸다. 임대인 점검 요청문에 상세 주소가 필요하면 앱에서 생성된 초안에 확인한 주소를 반영한다. 상세 `address`는 진단·요청문 생성 API의 모델 입력에 자동으로 포함하지 않는다. 요청문 편집본 저장 API는 추가하지 않는다.

## 인증과 버전

로그인 후 앱은 FastAPI 요청에 `Authorization: Bearer <access_token>`을 보낸다. 모든 API(`GET /health` 제외)는 인증을 확인하고, 기록·채팅 API는 소유권 또는 참여 권한을 확인한다. 사용자 ID는 검증한 토큰(`sub`)에서 결정한다.

`input_revision`은 기록 입력의 버전이다. 입력(`location`, `material`, `symptoms`, `region_id`, `photo_observations`) 변경은 버전 증가와 함께 원자적으로 처리하고, 생성 결과는 사용한 입력 버전이 현재 버전과 일치할 때 저장한다. 버전 충돌은 `409`로 반환한다.

## 기본 순서 (요청인 앱 5개 탭 기준)

로그인 후 요청인 앱은 **`소식` · `분석`(기본 탭) · `채팅` · `업체` · `정보`** 5개 탭을 제공한다. 채팅 탭은 별도 채팅 목록 화면을 연다.

1. 회원가입 후 프로필 저장을 완료하거나 기존 계정으로 로그인한다.
2. **소식지 탭**: `GET /support-programs`로 사용자 거주 지역 + 전국 주거 지원 사업을 페이지 단위(`limit`, `offset`)로 조회한다. 마감 공고는 `마감` 배지·흐림 처리와 하단 정렬로 표시하고, 카드 클릭 시 `GET /support-programs/{program_id}` 상세 요약과 외부 원문 URL을 연다. *(백엔드 구현 완료, 모바일 화면 후속)*
3. **분석 탭**: `POST /records`로 기록을 만들고, 분석 전 지역을 확인한 뒤 한 화면에서 사진 1~2장(1장 필수) + 위치 + 재질 + 선택 증상 메모를 입력해 `POST /records/{record_id}/analyze`를 호출한다. 선택한 지역은 기록 스냅샷으로 저장한다. 두 모델 경로가 모두 미설정이면 샘플 결과(`source=sample`)로 동작한다.
4. **분석 결과 페이지**: 심각도(`0~100%` 또는 `판단 보류`), `추정 원인`(AI 추정 안내·미확인 정보 포함), `해결방안`, `재발 방지책`을 확인한다.
   - `자가`가 아닌 거주 형태라면 필요 시 `POST /records/{record_id}/drafts/landlord`로 임대인 점검 요청문을 생성·복사한다.
   - 업체 상담이 필요하면 `GET /providers`로 업체를 조회한 뒤 실제 업체의 `채팅하기`로 `POST /chat/rooms`를 호출해 1:1 채팅방을 열고 하자 분석 요약을 자동 공유한다.
5. **채팅 탭**: `GET /chat/rooms`로 방별 미읽음 수를 포함한 목록을 보고, `/chat/ws`로 새 메시지를 받으며 `GET/POST /chat/rooms/{room_id}/messages`로 대화를 이어간다. 방에 들어가 이력을 받은 직후 `POST /chat/rooms/{room_id}/read`를 호출한다.
6. **정보 탭**: `GET/PUT /me/profile`로 프로필을 조회·수정하고, `GET /records`로 내 하자 분석 기록 목록을 불러와 과거 기록의 결과 페이지를 다시 연다.

## 내 정보와 하자 분석 기록 목록 (`GET /records`, 구현 완료)

`내 정보` 페이지의 **내 하자 분석 기록 목록**을 조회한다. 본인이 소유한 기록만 `updated_at` 내림차순(같으면 `created_at`, `id` 내림차순)으로 반환한다.

- 응답은 배열이며 항목 필드는 `record_id`, `location`, `material`, `symptoms`, `region_id`, `region_name`, `suspected_types`(예: `["곰팡이"]`), `severity_score`, `severity_level`, `created_at`, `updated_at`이다. 지역이 없으면 `region_id`·`region_name`은 `null`이다.
- 전체 진단·입력 버전·대화는 포함하지 않는다. 진단이 없으면 `suspected_types=[]`, `severity_score=null`, `severity_level=null`이다. `region_name`은 `regions.display_name`이다.
- 목록에서 항목을 선택하면 기존 `GET /records/{record_id}`로 전체 상세를 불러와 분석 결과 페이지를 다시 표시한다.
- 다른 사용자의 기록은 목록에 포함하지 않는다.

## 소식지 목록 페이지네이션 (`GET /support-programs`, 구현 완료)

- **쿼리**: `status`(`all` | `active`, 기본 `all`), `region_scope`(`national` | `local`, 선택), `region_id`(선택, 프로필 지역·상위 지역 UUID), `category`(선택, 아래 카테고리 키), `limit`(1~50, 기본 5), `offset`(0 이상, 기본 0)
- **응답**: `items`, `total`, `limit`, `offset`, `has_more`
- `total`은 `status`·`region_scope`·`region_id`·`category` 필터를 적용한 전체 수이고 `has_more = (offset + len(items)) < total`이다.
- `REPEATABLE READ` 트랜잭션에서 같은 `visible` CTE로 total과 페이지를 각각 조회하므로, `offset >= total`이어도 빈 `items`와 정확한 `total`, `has_more=false`를 반환한다.
- 기존 정렬(`is_closed ASC`, `housing_type_matched DESC`, 확정 마감일 오름차순, `source_checked_at DESC`, `title ASC`, `id ASC`)과 시드 중복 제거 규칙은 유지한다.

## 일괄 분석과 진단 (`POST /records/{record_id}/analyze`, 구현 완료)

분석 페이지에서 채팅 없이 사진(1~2장)과 위치·재질·선택 증상 메모를 한 번에 제출한다. 서버는 1단계 사진 관찰(YOLO·SAM·비전 LLM 보조)과 2단계 텍스트 진단을 분리한다. `YOLO_MODEL_PATH`와 `LLM_API_KEY`가 모두 미설정이면 입력값 기반 샘플 모드(`source=sample`)로 동작한다.

- **요청 (`multipart/form-data`)**:
  - `photos`: 이미지 파일 1~2장 (첫 번째 필수, 두 번째 선택)
  - `photo_roles`: 각 사진의 역할 (`overview` | `closeup`). 사진 수와 같아야 하며 서로 달라야 한다.
  - `external_analysis_consent`: 외부 사진 전송(Meta SAM·비전 LLM) 동의 여부 (`boolean`, 생략 시 `false`). 명시적 `true`일 때만 외부로 전송한다.
  - `location`: 하자 발견 위치 (필수 문자열, 공백만 불가)
  - `material`: 표면 재질 (필수 문자열, 공백만 불가)
  - `symptoms`: 선택 증상 메모 (`string | null`)
  - 파일은 JPEG·PNG·HEIC·HEIF, 한 장당 10MB 이하만 허용한다. 업로드 파일은 성공·실패 모두 닫고 원본을 저장하지 않는다.

- **사진 관찰 결과**: 사진별 `status`는 `not_analyzed`, `analyzed`, `failed` 중 하나이고 `source`는 `sample`, `yolo`, `yolo_sam`, `vision_llm` 중 하나다. 최상위 `photo_analysis.source`와 응답 `source`는 사진 출처를 합쳐 `yolo`, `yolo_sam`, `vision_llm`, `yolo_vision_llm`, `sample` 중 하나로 반환한다. YOLO와 비전 LLM 결과가 섞이면 `yolo_vision_llm`이다.
- **탐지 항목**: `object_id`, `class_id`, `label`, `raw_label`, `confidence`, `bbox`(원본 기준 반열린 xyxy), `image_size`([너비, 높이]), `area_ratio`(0~1, 이미지 전체 면적 대비 화면 점유 비율), `source=yolo`, `segmentation_status`, `mask`를 포함한다. SAM 마스크가 있으면 `area_ratio`는 마스크 픽셀 비율(bounds 스케일 반영)이고, 없으면 bbox 면적 비율이다. `mask`는 null 또는 `encoding=coco_rle`, `size`([높이, 너비]), `counts`, 시각화용 `svg_path`, 원본 기준 반열린 `bounds`, `source=sam-3.1`이다. RLE는 bounds 영역에 맞춰 배치한다.
- **라벨 정규화**: `crack`→`균열`, `paint_peel`/`peeling`→`벗겨짐`, `mold`/`mould`→`곰팡이`로 `label`을 정규화하고 원본 클래스명은 `raw_label`에 보존한다. 미등록 라벨은 원문을 유지한다.
- **비전 LLM 보조 관찰**: 동의와 `LLM_API_KEY`가 있고 사진별 YOLO 탐지가 0건이거나 YOLO 실행이 불가할 때만 그 사진을 긴 변 1280px JPEG로 전송한다. `vision_observation`은 `suspected_types`(`균열`·`벗겨짐`·`곰팡이`), `summary`, `approximate_location`, `unreadable_reason`을 포함하며 좌표는 만들지 않는다. 사진별 실패·판독 불가는 `status="failed"`로 남기고 전체 분석은 계속한다.
- **분할 상태**: `completed`, `no_mask`, `failed`, `unavailable`(키 미설정), `skipped_no_consent`다. SAM 실패 시 YOLO 결과는 유지한다. 사진당 최대 16개를 탐지한다. 실제 이미지 디코딩 실패·2,500만 픽셀 초과는 `422`다.
- **샘플 응답 예시 (`200 OK`)**:

```json
{
  "record_id": "<record UUID>",
  "input_revision": 1,
  "diagnosis_generation": 1,
  "photo_analysis": {
    "applied": false,
    "notice": "샘플 결과입니다. 실제 사진 분석과 외부 AI 호출은 수행하지 않았습니다. 입력한 위치·재질·증상만 사용했습니다.",
    "photos": [
      {
        "role": "overview",
        "status": "not_analyzed",
        "source": "sample",
        "detections": [],
        "vision_observation": null
      }
    ],
    "source": "sample"
  },
  "diagnosis": {
    "observations": "사진 분석은 수행되지 않았습니다. 입력한 위치(안방 창틀 아래), 재질(실리콘), 검은 곰팡이 의심 얼룩을 기준으로 만든 샘플 관찰 요약입니다.",
    "suspected_types": ["곰팡이"],
    "severity_score": 75,
    "severity_level": "high",
    "reason": "입력값 기준 샘플 심각도 75%(high)입니다. 곰팡이 관련 입력이 있었지만 실제 사진 분석 없이 만든 참고용 수치입니다.",
    "causes": [
      "창가 결로로 인한 표면 습기 축적 가능성",
      "실리콘·창틀 틈새의 습기 잔류 가능성"
    ],
    "estimation_notice": "이 결과는 사진을 실제로 분석하지 않고 입력한 위치·재질·증상만으로 만든 샘플입니다. 실제 AI 진단이나 현장 점검 결과가 아니며, 정확한 원인은 현장 확인이 필요합니다.",
    "recommended_action": "inspection",
    "care_steps": [
      "표면을 무리하게 긁거나 뜯지 말고 현재 상태를 유지하세요.",
      "누수·결로가 의심되면 임대인이나 관리실에 점검을 요청하세요."
    ],
    "supplies": ["마스크", "고무장갑", "마른 천", "곰팡이 제거제"],
    "prevention_tips": [
      "아침·저녁 짧게라도 맞통풍 환기를 유지하세요.",
      "결로가 맺히면 바로 물기를 닦아 습기를 남기지 마세요.",
      "같은 증상이 반복되면 원인 점검을 받으세요."
    ],
    "unknowns": [
      "사진에서 확인할 흔적의 범위와 정도(사진 분석 미수행)",
      "누수·결로 등 실제 원인",
      "이전 조치와 재발 여부"
    ],
    "work_type_id": null,
    "work_type_reason": "곰팡이 제거와 습기 원인 점검을 함께 진행하는 것이 적합합니다.",
    "source": "sample"
  },
  "source": "sample"
}
```

- **샘플 모드의 의미**: 두 모델 경로가 모두 미설정일 때만 `photo_analysis.applied=false`, 사진 상태 `not_analyzed`, `detections=[]`다. 관찰 요약·심각도·원인은 입력값만 사용한 참고용 샘플이며, 응답·진단의 `source`와 화면 안내로 실제 분석이 아님을 표시한다.
- **입력과 버전**: 제출한 `location`·`material`·`symptoms`·`region_id`가 실제로 달라지면 `input_revision`을 1 올리고 `diagnosis_generation`을 증가시킨다. 같은 입력이면 버전은 유지하고 생성 번호만 증가한다. 분석 중 다른 입력 변경이 발생하면 아무것도 저장하지 않고 `409`(`revision_conflict`)와 현재 `input_revision`을 반환한다. 원본 사진은 DB·로그에 저장하지 않고, Storage가 설정되면 비공개 버킷에 리사이즈 JPEG로 저장한다([ADR 0002](../adr/0002-private-storage-for-defect-photos.md)). 기록 상세의 `photos`는 단기 Signed URL 목록이다.
- **판단 보류**: 사진 흔적·비전 관찰·증상이 모두 없거나 모델이 근거 부족으로 `severity_score=null`을 반환하면 `severity_score=null`, `severity_level="undetermined"`, `suspected_types=[]`, 권장 대응 `inspection` 또는 `provider_consult`, `원인 점검` 작업으로 저장한다. `self_care`가 오면 `inspection`으로 보정한다.
- **심각도·용어·작업 검증**: 유효한 심각도는 서버가 `low`(0~39)·`medium`(40~69)·`high`(70~100)로 강제 정규화한다. 의심 유형은 `크랙`→`균열`, `박리`→`벗겨짐`으로 정규화한다. 작업 ID·이름이 DB `work_types`와 일치할 때만 저장하고 미일치·복합 원인은 `원인 점검`으로 폴백한다.
- **진단 실패**: `LLM_API_KEY`가 있는데 진단 호출·JSON 검증이 실패하면 `502`(`llm_error`), 제한 시간 초과는 `504`(`llm_timeout`)이며 기존 저장 결과를 유지한다. `YOLO_MODEL_PATH`만 있고 `LLM_API_KEY`가 없으면 `503`(`llm_unavailable`)이다.

## 진단 생성·재생성 (`POST /records/{record_id}/diagnosis`, 구현 완료)

- **쿼리**: `regenerate` (`boolean`, 기본 `false`)
- **동작**:
  1. 본인 소유 기록만 허용하며 없거나 다른 사용자 기록은 `404`다.
  2. `regenerate=false`이고 `diagnosis_revision == input_revision`이면 모델을 호출하지 않고 기존 진단을 반환한다.
  3. 재생성 또는 입력 변경 상태에서는 `location`과 `material`이 모두 있어야 하며 누락 시 `422`(`invalid_request`)다.
  4. 저장된 `photo_observations`(없으면 사진 미분석), 현재 위치·재질·마스킹한 증상, DB 작업 종류로 텍스트 LLM을 호출한다. 호출 동안 행 잠금을 유지하지 않는다.
  5. 저장 직전 `FOR UPDATE`로 다시 잠가 `input_revision`이 생성 시작 값과 같은지 확인하고, 다르면 저장 없이 `409`(`revision_conflict`)다.
  6. 저장 시 `diagnosis`, `diagnosis_revision`, `diagnosis_generation+1`, `updated_at`을 갱신한다.
- **응답**: `record_id`, `input_revision`, `diagnosis_generation`, `diagnosis`, `source`(`llm` | `sample`).
- **오류**: 모델 키 미설정은 기존 진단이 있어도 항상 `503`(`llm_unavailable`), 호출·형식 오류 `502`(`llm_error`), 제한 시간 초과 `504`(`llm_timeout`). 실패 시 기존 진단은 유지된다.

## 하자 사진 Storage (구현 완료)

- 하자 사진은 `SUPABASE_STORAGE_BUCKET`(기본 `defect-photos`) **비공개** 버킷에 `{owner_id}/{record_id}/{role}_{uuid}.jpg` 경로로 저장한다.
- 서버는 리사이즈(긴 변 1600px)·EXIF 제거 JPEG를 업로드하고 `records.photo_files`에 `role`, `storage_path`, `width`, `height`를 남긴다.
- `GET /records/{record_id}`는 기록 소유자에게만 `photos: [{role, url, expires_at, width, height}]`를 반환한다. URL은 `STORAGE_SIGNED_URL_TTL_SECONDS`(기본 300초) 단기 Signed URL이다.
- `GET /quote-requests`, `GET /quote-requests/{request_id}`도 요청서 `photo_files` 스냅샷의 Signed URL을 **권한 확인 후** 반환한다.
- `SUPABASE_STORAGE_KEY`(또는 `SUPABASE_SERVICE_ROLE_KEY`)가 없으면 업로드·서명을 생략하고 `photo_files=[]`, `photos=[]`로 동작한다. 서버 키는 모바일·로그·응답에 노출하지 않는다.
- 업로드 후 DB 저장이 실패·충돌하면 방금 업로드한 객체를 best-effort 삭제한다. 재분석 시 이전 `photo_files` 객체는 기존 요청서가 참조할 수 있어 삭제하지 않는다.

## 견적 요청서·제안서·수락 (구현 완료)

| API | 역할 | 동작 |
| --- | --- | --- |
| `POST /quote-requests` | 요청인 | 본인 기록을 1:N 공개 요청서로 등록한다. 진단 없으면 `409 diagnosis_required`, 같은 기록의 진행 중 요청서가 있으면 `409 request_already_open` |
| `GET /quote-requests` | 공통 | 요청인은 본인 요청서 최신순, 업체는 지역·특화 분야가 모두 맞는 진행 중 요청서 + 본인이 제안서를 보낸 요청서만 조회 |
| `GET /quote-requests/{request_id}` | 공통 | 요청인 본인·매칭 업체·제안 참여 업체만 조회. 요청인은 모든 제안서, 업체는 본인 제안서만 노출 |
| `POST /quote-requests/{request_id}/proposals` | 업체 | 지역·특화 분야 매칭과 `open` 상태를 잠금 하에 확인하고 업체당 1건 제안 |
| `POST /quote-requests/{request_id}/proposals/{proposal_id}/accept` | 요청인 | 수락 1건 + 나머지 `rejected` + 요청서 `accepted`를 원자 처리 |
| `POST /quote-requests/{request_id}/cancel` | 요청인 | 요청서 `cancelled` + 대기 제안서 `rejected` |

- 요청서 생성 시 지역은 요청값 → 기록 지역 → 프로필 지역, 작업 종류는 요청값 → 진단 추천 → `원인 점검` 순으로 결정한다. 위치는 기록에서 필수, 메모는 요청값 또는 증상 메모를 쓴다.
- 사진 경로와 `severity_score`·`severity_level`·`suspected_types`는 발행 시점 스냅샷으로 저장한다.
- 상태는 요청서 `open`/`accepted`/`cancelled`, 제안서 `pending`/`accepted`/`rejected`다. DB 부분 유일 인덱스로 요청서당 공개 1건·수락 1건, 복합 유일 제약으로 업체당 제안 1건을 강제한다.
- 매칭 업체·제안 업체가 아니거나 다른 요청인은 `404`다. 업체는 여전히 원본 기록·프로필 API에 접근할 수 없다. 수락 전에도 `POST /chat/rooms`로 1:1 채팅을 열 수 있다.
- `POST /records/{record_id}/drafts/provider`는 삭제하지 않고 요청서 메모·채팅 첫 문의 보조용으로 유지한다.

## 이후 남은 설계

- 소식지 보조금24 동기화를 수동 명령에서 주기 실행으로 확장한다. 나머지 4단계 항목은 구현 완료다.

## 요청문 (`landlord`, `provider`, 구현 완료)

요청문 종류는 `landlord`(임대인 점검 요청문) 또는 `provider`(업체 견적 요청문)로 구분하며, 두 값 외에는 경로에서 `422`로 거부한다.

| API | 동작 |
| --- | --- |
| `POST /records/{record_id}/drafts/{kind}` | 본인 기록의 현재 입력과 진단으로 생성한다. 입력 버전과 진단 생성 번호가 모두 현재 값과 같은 저장본이 있으면 모델을 호출하지 않고 재사용한다. |
| `POST /records/{record_id}/drafts/{kind}?regenerate=true` | 모델로 새로 생성하고, 성공했을 때만 최신본을 교체한다. 실패하면 기존 값을 유지한다. |
| `GET /records/{record_id}/drafts/{kind}/template` | 모델을 호출하지 않고 현재 입력의 확인된 사실(위치·재질·증상)과 진단 참고 내용을 채운 기본 양식을 반환한다. |

생성 응답 예시 (`200 OK`):

```json
{
  "kind": "landlord",
  "text": "안녕하세요. 아래 하자에 대한 임대인·관리실 점검 요청을 드립니다.\n\n[확인된 내용]\n- 위치: 안방 창틀 아래\n- 재질: 실리콘\n- 증상 메모: 검은 곰팡이 의심 얼룩\n\n[진단 참고(추정)]\n- 의심 유형: 곰팡이\n...",
  "input_revision": 1,
  "diagnosis_generation": 1
}
```

기본 양식 응답 예시 (`200 OK`):

```json
{
  "kind": "provider",
  "text": "안녕하세요. 아래 하자에 대한 수리 업체 견적 요청을 드립니다.\n\n[확인된 내용]\n- 위치: 안방 창틀 아래\n...",
  "input_revision": 1,
  "diagnosis_generation": 1
}
```

- 생성 규칙: 관찰·사용자 입력, 추정 원인(확인 필요), 추가 확인 필요 사항, 요청 사항을 구분하고 미확인 원인을 단정하지 않는다.
- 진단이 없으면 생성은 `409`(`diagnosis_required`)이고, 기본 양식은 진단 없이도 `200`이다. 이때 `diagnosis_generation`은 `null`이다.
- 생성 중 입력이 바뀌면 `409`(`revision_conflict`)와 현재 `input_revision`, 진단이 교체되면 `409`(`diagnosis_conflict`)를 반환하고 아무것도 저장하지 않는다. 실패한 생성은 기존 저장본을 덮어쓰지 않는다.
- 모델 키 미설정은 `503`(`llm_unavailable`), 호출·응답 형식 오류는 `502`(`llm_error`), 제한 시간 초과는 `504`(`llm_timeout`)이다. 샘플 문구를 생성 결과로 저장하거나 반환하지 않는다.
- 외부 모델에는 기록의 위치·재질·증상과 진단 결과만 전송한다. 프로필 닉네임·등록 주소·거주 형태·이메일은 전송하지 않으며, 증상 메모의 이메일·휴대전화 번호는 전송 전에 제거한다. 프롬프트·응답·요청 본문은 로그에 남기지 않는다.
- **미확정**: 증상 메모 원문을 외부 모델 입력으로 계속 사용할지와 동의·고지 방식은 팀 회의 전이다. 현재 동작은 위 범위·마스킹을 유지하며, 결정 시 요청 필드·오류 응답·모바일 동의 UI를 함께 바꾼다.
- `자가` 거주 형태 요청인에게 임대인 요청문을 기본 숨기는 것은 모바일 UI 범위다. 서버에 역할·거주 형태 기반 차단 규칙을 두지 않는다.
- 편집본 저장 API는 없다. 편집·복사는 앱 화면에서 유지하고, 등록 주소를 반영한 문구도 서버로 다시 저장하지 않는다.

## 소식지 조회 (`GET /support-programs`, 구현 완료)

`GET /support-programs`는 로그인 사용자의 프로필 `region_id`와 `housing_type`을 기준으로, 해당 지역·상위 지역(예: 용인시 → 경기도)·전국 공고를 반환한다. `region_id` 필터는 이 가시 범위 안에서만 동작하며, 다른 지역 ID를 보내면 빈 목록을 반환한다.

- `status=all`(기본)은 마감 공고를 포함하고, `status=active`는 마감되지 않은 공고만 반환한다.
- `region_scope`로 전국(`national`)·지역(`local`)을 나누고, `region_id`로 프로필 지역·상위 지역 중 하나를 지정한다. 예: 용인시 사용자는 `전국`·`경기도`·`경기도 용인시`로 필터할 수 있다. 모바일 소식지 화면은 프로필 지역 기준으로 고정하고 지역 선택 UI를 두지 않는다.
- 정렬: **진행 중(`is_closed=false`) 먼저 → 거주 형태 태그 일치(`housing_type_matched=true`) 우선 → 확정 마감일이 이른 순 → 출처 확인 시각 최신순**. 마감 공고는 하단에 배치한다.
- `housing_type_matched`는 사용자의 거주 형태가 공고 태그와 겹치는지만 표시한다. 태그 일치는 실제 신청 자격을 확정하지 않는다.
- `categories`는 제목·요약 키워드로 분류한 참고 카테고리다. `monthly_rent_support`(월세), `deposit_loan`(보증금·대출), `housing_cost`(주거비), `repair`(수리·개선), `brokerage_fee`(중개비), `supply`(입주·공급), `other`(기타) 중 복수일 수 있으며, `category` 쿼리로 필터한다. 카테고리도 신청 자격을 확정하지 않는다.
- 검증 시드와 같은 제목(끝의 `사업` 제외)·기관·지역의 보조금24 API 행은 목록에서 시드로 대체해 중복 표시하지 않는다. API 행 자체는 상세 ID로 조회할 수 있다.
- `deadline_kind`로 신청기한 상태를 구분한다.
  - `fixed`: 명확히 해석한 날짜가 있고 `deadline_date`가 채워짐. 보조금24 `기간설정`의 단일 기간 또는 명확한 단일 날짜만 해당한다.
  - `always_open`: 보조금24 `상시신청` 또는 공식 원문이 상시·연중 신청임
  - `unknown`: 원문이 없거나 `접수기관별상이`·복수 날짜·범위·조건부 등으로 모호함
- `is_closed`는 `deadline_kind="fixed"`이고 `deadline_date`가 **한국 시간 기준 오늘보다 이전**일 때만 `true`다. 마감일 당일은 아직 마감이 아니며, 상시·기한 불명은 `false`다.
- 프로필이 없으면 `404`, 결과가 없으면 `200`과 빈 배열을 반환한다. DB 오류를 빈 목록으로 대체하지 않는다.

목록 응답 예시 (`200 OK`):

```json
[
  {
    "id": "<program UUID>",
    "title": "용인청년 부동산 중개보수 감면",
    "summary": "민관 협력을 통해 ...",
    "organization_name": "용인시",
    "region_scope": "local",
    "region_name": "경기도 용인시",
    "target_housing_types": ["monthly_rent", "jeonse"],
    "categories": ["brokerage_fee"],
    "housing_type_matched": true,
    "deadline_text": "2026-01-01 00:00 ~ 2026-12-31 00:00",
    "deadline_date": "2026-12-31",
    "deadline_kind": "fixed",
    "is_closed": false,
    "detail_url": "https://youth.yongin.go.kr/web/main/youthPolicy/view?bizId=A2026021000000000000055001",
    "source": "seed",
    "source_attribution": "용인청년포털 · 용인시",
    "source_checked_at": "2026-11-20T04:00:00Z",
    "updated_at": "2026-11-20T04:00:00Z"
  }
]
```

`GET /support-programs/{program_id}`는 인증된 사용자라면 프로필 없이도 조회할 수 있으며, 목록 공통 필드에 다음 상세 필드를 더한다.

- `support_target`: 공식 원문의 지원 대상·자격
- `support_content`: 공식 원문의 지원 내용
- `selection_criteria`: 공식 원문의 선정 기준(없으면 `null`)
- `apply_method`: 공식 원문의 신청 방법(없으면 `null`)
- `synced_at`: 보조금24 API 마지막 동기화 시각(검증 시드는 `null`)

```json
{
  "id": "<program UUID>",
  "title": "청년월세 지원사업",
  "summary": "...",
  "organization_name": "국토교통부",
  "region_scope": "national",
  "region_name": "전국",
  "target_housing_types": ["monthly_rent"],
  "categories": ["monthly_rent_support"],
  "support_target": "19세~34세 독립거주 무주택 청년 중 ...",
  "support_content": "월세로 거주하는 청년을 대상으로 ...",
  "selection_criteria": null,
  "apply_method": "주소지 관할 주민센터에 청년 본인이 방문하거나 복지로에서 온라인으로 신청",
  "deadline_text": "2026년 신규수혜자 신청접수 기간: 3.30(월) 09:00 ~ 5.29(금) 16:00까지",
  "deadline_date": "2026-05-29",
  "deadline_kind": "fixed",
  "is_closed": true,
  "detail_url": "https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004661",
  "source": "seed",
  "source_attribution": "복지로 · 국토교통부",
  "source_checked_at": "2026-11-20T04:00:00Z",
  "synced_at": null,
  "updated_at": "2026-11-20T04:00:00Z"
}
```

- 원문 URL은 `http`·`https`만 허용한다. 클라이언트가 공고를 생성·수정·삭제하는 API는 두지 않는다.
- 출처 표시: 시드·동기화 데이터 모두 `source_attribution`을 포함한다. 보조금24 동기화 행의 출처는 `행정안전부 대한민국 공공서비스(혜택) 정보 · 공공데이터포털`이다.
- `source_checked_at`은 해당 행의 출처를 마지막으로 확인한 시각이고, `synced_at`은 외부 API에서 마지막으로 갱신한 시각이다. 모바일은 두 값을 구분해 표시할 수 있다.

## 업체 조회 (`GET /regions`, `GET /work-types`, `GET /providers`, `GET /providers/{provider_id}` 구현 완료)

`GET /regions`는 회원 프로필의 거주 지역 선택과 소식지·업체 검색에 사용할 지역 ID와 시·군·구가 포함된 표시 이름을 반환한다. 응답은 `{ "region_id", "name", "display_name" }` 배열이며 `display_name` 순으로 정렬한다. 마이그레이션 `007_profiles_and_regions.sql`은 시연 지역 `용인`(`name="yongin"`, `display_name="경기도 용인시"`)을 시드하고, `008_support_programs.sql`은 상위 지역 `경기도`(`name="gyeonggi"`)를 추가해 용인시의 상위 지역으로 연결한다.

`GET /work-types`는 작업 ID와 이름을 `{ "work_type_id", "name" }` 배열로 반환한다. `010_chat_and_provider_accounts.sql`이 `곰팡이 제거`, `균열 보수`, `벽지·도장 보수`, `원인 점검`을 시드한다. 앱은 진단의 추천 작업을 미리 선택할 수 있다.

업체 검색 전 앱은 등록 주소·거주 지역이 맞는지 확인하고 확인한 거주 지역 ID를 사용한다. `GET /providers?region_id=<UUID>&work_type_id=<UUID>`에서 `region_id`는 필수, `work_type_id`는 선택이다. 작업 종류를 생략하면 해당 지역 전체 업체를, 전달하면 지역과 특화 분야가 모두 맞는 업체를 별점 내림차순(`rating DESC`, `review_count DESC`, `name ASC`, `id ASC`)으로 반환한다.

응답 예시 (`200 OK`, 실제 후보):

```json
{
  "providers": [
    {
      "provider_id": "<provider UUID>",
      "name": "용인 곰팡이 수리",
      "phone": "031-000-0000",
      "rating": 4.8,
      "review_count": 24,
      "description": "결로·곰팡이 원인 점검과 도배 보수를 함께 진행합니다.",
      "specialty_work_types": [
        {"work_type_id": "<work type UUID>", "name": "곰팡이 제거"},
        {"work_type_id": "<work type UUID>", "name": "원인 점검"}
      ],
      "chat_available": true,
      "is_sample": false
    }
  ],
  "is_sample": false
}
```

실제 후보가 없을 때의 응답은 `is_sample=true`이고 항목은 `phone=null`, `rating=0.0`, `review_count=0`, `specialty_work_types=[]`, `chat_available=false`다. 샘플은 `providers` 테이블에 없는 고정 UUID다.

- `chat_available`은 사전 등록된 업체 계정(`providers.account_user_id`)이 연결되어 앱 내 채팅이 가능한지 여부다.
- 실제 후보가 하나라도 있으면 `is_sample=false`이고 샘플을 섞지 않는다.
- 등록되지 않은 지역·작업 ID는 `422`, DB 오류는 `500`이다. DB 오류를 빈 목록이나 샘플로 대체하지 않는다.
- `GET /providers/{provider_id}`는 인증된 사용자에게 평점, 리뷰 수, 소개, 주소, 영업시간, 경력 연수, 출장 가능 지역(`regions`), 특화 분야(`work_types`)를 반환한다. 없는 업체·샘플 UUID는 `404`, 잘못된 UUID는 `422`다. 상세 API의 `is_sample`은 항상 `false`다.
- `GET`·`PUT /me/profile`의 `provider_id`는 `providers.account_user_id`가 현재 사용자와 연결된 경우 업체 UUID, 요청인이면 `null`이다. `PUT` 요청 본문에서 `role`/`provider_id`를 지정할 수 없다(`422`).
- `013_provider_details.sql`이 평점·리뷰·소개·주소·영업시간·경력을 추가한다. `014_yongin_provider_seed.sql`은 팀 확인 자료가 없어 실제 업체 행을 넣지 않고, 공식 출처 확인 후 채울 idempotent 템플릿만 둔다. 앱은 `is_sample=true`일 때 시연 안내를 표시한다.

## 업체–요청인 1:1 채팅 (`/chat/*`, 구현 완료)

방 생성·목록·이력 조회·메시지 저장·읽음 처리는 FastAPI REST API, 실시간 수신은 인증된 FastAPI WebSocket으로 구현했다. 푸시 알림은 추가하지 않는다. 읽음 시점은 **앱이 채팅방에 들어가 메시지 이력을 받은 직후**로 정했다. 앱은 화면에 표시한 마지막 메시지까지 읽음 처리하고, 서버는 그 시각을 저장한다. 같은 계정의 다른 기기도 같은 서버 읽음 상태를 공유한다.

| API | 동작 |
| --- | --- |
| `GET /chat/rooms` | 로그인한 요청인 또는 업체 계정이 참여 중인 방을 `last_message_at` 내림차순(없으면 `created_at`)으로 반환한다. 상대방 이름 `counterpart_name`, 최근 메시지 앞 80자 `last_message_preview`, `latest_record_id`, 방별 `unread_count`를 포함한다. |
| `POST /chat/rooms` | 요청인이 `{ "provider_id": "<UUID>", "record_id": "<UUID>?" }`를 보내 방을 생성하거나 재사용한다. `record_id`가 있으면 서버가 만든 하자 요약을 `record_summary` 메시지로 공유한다. 새 요약은 WebSocket `message` 이벤트로도 전달한다. |
| `POST /chat/rooms/{room_id}/read` | 참여자가 방의 상대방 메시지를 읽음으로 표시한다. 서버가 읽음 시각을 기록하고 `{ "room_id", "last_read_at", "unread_count" }`를 반환한다. |
| `GET /chat/rooms/{room_id}/messages` | 참여자만 조회한다. `created_at`, `id` 오름차순이며 `limit`(기본 50, 최대 100)·`offset`으로 나눈다. 재연결 후 놓친 메시지를 맞출 때도 이 API를 쓴다. |
| `POST /chat/rooms/{room_id}/messages` | 참여자가 `{ "client_message_id": "<UUID>", "content": "..." }`를 보내 저장한다. 발신자·역할은 토큰과 방 참여 정보로 정한다. 새로 저장된 메시지는 참여자 WebSocket으로 전달한다. |
| `WS /chat/ws` | 인증된 사용자의 실시간 이벤트 스트림. 참여 중인 모든 방의 새 메시지를 받는다. |

`POST /chat/rooms` 응답 예시 (`200 OK`, 기존 방이면 같은 `room_id`):

```json
{
  "room_id": "<room UUID>",
  "requester_id": "<requester UUID>",
  "provider_id": "<provider UUID>",
  "provider_name": "용인 곰팡이 수리",
  "latest_record_id": "<record UUID>",
  "last_message_at": "2026-11-20T04:00:00Z",
  "created_at": "2026-11-20T04:00:00Z",
  "updated_at": "2026-11-20T04:00:00Z"
}
```

`GET /chat/rooms` 항목 예시(추가 필드):

```json
{
  "room_id": "<room UUID>",
  "provider_name": "용인 곰팡이 수리",
  "counterpart_name": "용인 곰팡이 수리",
  "last_message_preview": "내일 오후에 방문 점검 가능할까요?",
  "last_message_at": "2026-11-20T04:10:00Z",
  "unread_count": 2
}
```

읽음 처리 응답 예시:

```json
{
  "room_id": "<room UUID>",
  "last_read_at": "2026-11-20T04:11:00Z",
  "unread_count": 0
}
```

WebSocket 이벤트 예시:

```json
{ "type": "ready", "user_id": "<requester UUID>" }
{ "type": "message", "room_id": "<room UUID>", "message": { "message_id": "...", "content": "네, 내일 방문 가능합니다", "created_at": "2026-11-20T04:12:00Z" } }
```

공유되는 `record_summary` 메시지 예시 (`GET .../messages`의 항목):

```json
{
  "message_id": "<message UUID>",
  "room_id": "<room UUID>",
  "sender_id": "<requester UUID>",
  "sender_role": "requester",
  "message_type": "record_summary",
  "record_id": "<record UUID>",
  "content": "[하자 분석 요약]\n위치: 안방 창틀 아래\n재질: 실리콘\n증상: 검은 곰팡이 의심 얼룩\n의심 유형: 곰팡이\n심각도: 75%\n추정 원인: 창가 결로로 인한 표면 습기 축적 가능성",
  "payload": {
    "record_id": "<record UUID>",
    "location": "안방 창틀 아래",
    "material": "실리콘",
    "symptoms": "검은 곰팡이 의심 얼룩",
    "suspected_types": ["곰팡이"],
    "severity_score": 75,
    "severity_level": "high",
    "causes": ["창가 결로로 인한 표면 습기 축적 가능성"],
    "diagnosis_source": "sample",
    "input_revision": 1,
    "diagnosis_generation": 1
  },
  "client_message_id": "<서버 발급 UUID>",
  "created_at": "2026-11-20T04:00:00Z"
}
```

메시지 목록 응답 예시 (`200 OK`):

```json
{ "messages": [], "limit": 50, "offset": 0, "has_more": false }
```

- **방 생성·재사용**: `(requester_id, provider_id)` 유일 제약으로 동시 요청에도 방이 하나만 생긴다. `provider_id`가 없으면 `404`, 샘플 업체(`is_sample=true`, DB에 없음)도 `404`, 계정이 연결되지 않은 업체는 `422`(`invalid_request`), 업체 계정이 직접 방을 만들면 `422`다.
- **요약 공유**: 서버가 저장된 기록·진단으로 요약을 만든다. 클라이언트가 보낸 요약·메시지 본문은 받지 않는다(`extra="forbid"`로 `422`). 같은 방에 같은 기록·같은 요약(`payload` 동일)이 이미 있으면 다시 공유하지 않는다. 진단을 다시 생성하면 요약이 달라져 새로 공유된다.
- **개인정보**: 요약과 응답에는 등록 주소·이메일·닉네임·거주 형태·원본 사진을 담지 않는다. 업체는 공유된 요약만 볼 수 있고 `GET /records/{record_id}` 등으로 원본 기록·프로필에 접근할 수 없다(비소유자 `404`).
- **메시지 멱등성**: 같은 `client_message_id`와 같은 내용 재전송은 기존 메시지를 반환하고, 같은 ID에 다른 내용은 `409`(`message_conflict`)다. 메시지 본문은 앞뒤 공백을 제거하며 공백만 불가, 최대 2000자다.
- **권한**: 요청인 본인 또는 해당 업체 `account_user_id`만 방·메시지에 접근한다. 다른 요청인·다른 업체·비참여자는 `404`다.
- **정렬·페이지**: 메시지는 `created_at`, `id` 오름차순이다. 메시지는 수정·삭제되지 않으므로 `offset`이 안정적이다.
- **미읽음 수**: `GET /chat/rooms`의 `unread_count`는 내가 보내지 않은 메시지 중 마지막 읽음 시각 이후에 생성된 수다. 본인이 보낸 메시지는 세지 않는다. 읽음 시각이 없으면 상대방의 모든 메시지를 미읽음으로 센다.
- **읽음 처리**: 앱은 방에 들어가 `GET .../messages`로 이력을 받은 직후 `POST .../read`를 호출한다. 서버는 `now()`를 저장하므로 클라이언트 시계를 신뢰하지 않는다. 같은 계정의 다른 기기는 다음 목록·읽음 응답에서 같은 값을 본다. 읽음 처리와 동시에 도착한 메시지는 응답의 `unread_count`에 남을 수 있다.
- **WebSocket 인증**: `ws://<API>/chat/ws`에 연결한다. `Authorization: Bearer <access_token>` 헤더를 우선 사용하고, 헤더를 보낼 수 없는 클라이언트는 `?access_token=<JWT>` 쿼리를 쓴다. 누락·만료·서명 오류면 `4401`로 닫는다. 토큰이 쿼리에 남을 수 있으므로 서버·프록시 접근 로그에서 쿼리를 기록하지 않는다.
- **WebSocket 이벤트**: 연결 직후 `{"type":"ready","user_id":"<UUID>"}`를 받는다. 새 메시지는 `{"type":"message","room_id":"<UUID>","message":{...ChatMessageOut}}`로 전달된다. REST 전송의 응답과 같은 메시지 객체이며, 재전송 멱등으로 기존 메시지를 반환할 때는 이벤트를 다시 보내지 않는다. 서버는 클라이언트 텍스트 프레임을 무시한다.
- **재연결·놓친 메시지**: 서버는 이벤트를 재전송하지 않는다. 클라이언트는 연결이 끊기면 백오프 후 다시 연결하고, `GET /chat/rooms`로 미읽음 수·`last_message_at`을, `GET .../messages?limit=50&offset=<받은 개수>`로 누락 메시지를 맞춘다. `has_more=true`면 `offset + limit`으로 이어서 조회한다.
- **다중 서버 제한**: 현재 WebSocket 연결·브로드캐스트는 API 프로세스 메모리에 있다. 단일 프로세스 시연에는 충분하지만, 여러 워커·인스턴스로 확장하면 공유 브로커가 필요하다.
- 기존 `records/messages`(AI 추가 질문) 테이블과는 별도이며 서로 재사용하지 않는다.

## 오류 응답 초안

오류는 `code`와 사용자에게 보여줄 `message`를 포함한다. 버전 충돌 시 현재 입력 버전도 제공한다.

| 상황 | 상태 코드 |
| --- | --- |
| 인증 실패 또는 만료 | 401 |
| 기록·프로필·지원 사업·채팅방을 찾지 못했거나 접근 권한 없음 | 404 |
| 입력 버전 충돌, 진단 교체 충돌, 동일 메시지 ID의 내용 충돌 | 409 |
| 요청 필드·거주 형태·검색 코드·업로드 파일이 유효하지 않거나 프로필의 지역·닉네임 또는 `status` 쿼리가 유효하지 않음 | 422 |
| 외부 모델 또는 공공 API 호출·응답 형식 오류 | 502 |
| 요청문 생성 모델 키 미설정 | 503 |
| 외부 모델 또는 공공 API 응답 제한 시간 초과 | 504 |

일괄 분석 내 사진별 분석 성공·실패는 분석 응답의 `photo_analysis` 안에서 구분한다. 전체 요청 처리 실패는 오류 응답으로 반환한다. 진단·요청문 생성 실패 시 기존 입력과 유효 결과를 유지한다. 진단 생성 실패는 정보 부족에 따른 판단 보류(`severity_score=null`)와 구분한다.

## 기존 구현 · MVP 미사용(보류): AI 추가 질문 대화 API

아래 엔드포인트는 현재 저장소(`apps/api/app/records.py`, `apps/api/app/sample_questions.py`)에 구현·테스트되어 있으나, 분석 페이지 채팅창 제거 결정에 따라 **현재 MVP 흐름에서는 호출하지 않는다**. 추후 설문/객관식 추가 질문을 도입하기로 결정할 경우 참고·재사용하기 위해 기존 확정 계약을 기록해 둔다.

- **`POST /records/{record_id}/messages`**: `client_message_id`, `question_id?`, `selected_option_id` 또는 `content`, `input_revision`을 받아 사용자 메시지를 저장하고 `input_revision`을 1 올린다. `(record_id, client_message_id)` 멱등성 및 내용 충돌 시 409(`message_conflict`)를 반환한다.
- **`PUT /records/{record_id}/messages/{message_id}`**: `content`, `input_revision`을 받아 과거 사용자 메시지를 수정한다. 내용이 다르면 이후 대화·질문을 삭제하고 `input_revision`을 올린다.
- **`POST /records/{record_id}/next-question`**: 요청 본문 없이 현재 기록과 대화를 읽어 `sample_questions.py`의 시연 규칙(`source="sample"`, 창가 얼룩 2문항: `recurred`·`wiped`)을 반환하고 `next_question_result`에 캐시한다.

## 남은 연동 확인

- 실제 모델 연동 시 `POST /records/{record_id}/analyze`의 YOLO·비전 LLM·텍스트 LLM 인증·요청·응답·좌표 형식과 배포 환경 제한 시간
- 실제 `LLM_API_KEY`·모델로 요청문 생성 품질·비용·제한 시간 확인(현재 테스트는 고정 응답 대체)
- 용인시 실제 업체·연락처·출장 지역·작업 데이터와 사전 등록 업체 계정
- 확정된 WebSocket·방별 미읽음 수의 구현, 읽음 처리·인증·재연결·이벤트 계약 설계(푸시 알림 도입 여부는 미정)
- 진단 신뢰도 필드의 정의·산정 근거·검증·필드 계약 확정 및 구현
- 보조금24 API(`gov24/v3/serviceList`) 동기화의 실제 운영 키·응답 최신성 검증과 주거 필터 키워드 보정
