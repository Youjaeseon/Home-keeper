# MVP API 계약 초안

[백엔드 설계](BACKEND_DESIGN.md)와 [DB 설계](DB_DESIGN.md)의 합의를 요청·응답으로 구체화한 초안이다. 경로·필드명은 앱 담당자와 최종 확인할 대상이다. 아래 UUID 값은 문서에서 읽기 쉽도록 자리표시자로 적었다.

## 문서 범위

현재 코드에 구현된 API는 기록 생성·조회·수정(`POST /records`, `GET /records/{record_id}`, `PATCH /records/{record_id}`), 내 기록 목록(`GET /records`), 사진·위치·재질 일괄 분석(`POST /records/{record_id}/analyze`), 프로필(`GET/PUT /me/profile`), 지역 목록(`GET /regions`), 주거 지원 사업 소식지(`GET /support-programs`, `GET /support-programs/{program_id}`), 요청문 생성·기본 양식(`POST /records/{record_id}/drafts/{kind}`, `GET /records/{record_id}/drafts/{kind}/template`), 작업 종류·업체 검색(`GET /work-types`, `GET /providers`), 1:1 채팅(`GET/POST /chat/rooms`, `GET/POST /chat/rooms/{room_id}/messages`)이다. 이미 구현된 `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`은 분석 채팅창 제거에 따라 **현재 MVP 미사용(보류/레거시)** 상태이며, 문서 하단에 참고용으로 분리했다.

실제 모델 기반 일괄 분석·진단 재생성과 실시간 채팅 수신 방식은 아직 미확정·미구현이다. 요청문 생성은 서버에서 단일 LLM 제공사(OpenAI 호환 Chat Completions)를 사용한다. 실행 절차는 [개발 환경·DB·테스트 가이드](../guides/DEVELOPMENT.md), 호출 예시와 구현 메모는 [API 사용 가이드](../guides/API_USAGE.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `POST /records`는 201과 `record_id`, `input_revision`(최초 0)을 반환한다.
- `GET /records/{record_id}`는 저장된 입력(`location`, `material`, `symptoms`, `photo_observations`)과 `diagnosis`, `drafts`의 생성 당시 버전 및 `is_current`를 반환한다. *(구현본에는 레거시 `questions`, `messages`, `next_question` 필드도 함께 포함된다.)*
- `PATCH /records/{record_id}`는 `location`·`material`·`symptoms`를 받고 `input_revision`을 요구하지 않는다. 실제 값이 바뀔 때만 버전을 올리며, 명시한 `null`은 값을 지운다.
- `POST /records/{record_id}/analyze`는 사진 1~2장과 위치·재질·증상·외부 분석 동의를 multipart로 받아 입력값 기반 샘플 진단을 저장한다. 자세한 계약은 아래 일괄 분석 섹션을 따른다.
- 공통 오류 형식은 `{ "code", "message", "input_revision"? }`이다. 처리하지 못한 서버·DB 오류는 내용을 노출하지 않고 500 `internal_error`로 반환한다.
- 요청문은 `input_revision`과 `diagnosis_generation`이 모두 같은 저장본만 재사용하고, `regenerate=true`일 때만 모델을 다시 호출한다. 실패 시 기존 저장본과 기본 양식을 유지한다.
- 채팅방은 `(requester_id, provider_id)` 유일 제약으로 하나만 존재하고, 메시지는 `(room_id, client_message_id)` 유일 제약으로 재전송을 멱등 처리한다. 메시지 목록은 `created_at`, `id` 오름차순이며 `limit`·`offset` 페이지를 사용한다.
- *(MVP 미사용/보류)* `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`의 구현 확정 사항은 문서 하단 레거시 섹션에 유지한다.

## 회원가입과 프로필 (프로필 API 구현 완료)

일반 회원가입은 `요청인` 전용이다. 앱에서 Supabase Auth로 **이메일·비밀번호** 계정을 만들고, 회원가입 과정에서 `닉네임`, `거주 지역`(필수), `등록 주소`(선택), `거주 형태`(`월세`, `전세`, `반전세`, `자가`, `기타`)를 입력받는다. 인증 가능한 세션을 얻은 뒤 FastAPI에 프로필을 저장한다. 이메일 확인이 필요한 환경은 확인 후 동일 계정으로 프로필 등록을 완료한다. 계정 생성 후 프로필 저장에 실패하면 프로필 저장만 재시도한다. 시연용 `업체` 계정은 Supabase Auth와 `profiles`(`role="provider"`)에 사전 등록한다.

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

`input_revision`은 기록 입력의 버전이다. 입력(`location`, `material`, `symptoms`, `photo_observations`) 변경은 버전 증가와 함께 원자적으로 처리하고, 생성 결과는 사용한 입력 버전이 현재 버전과 일치할 때 저장한다. 버전 충돌은 `409`로 반환한다.

## 기본 순서 (요청인 앱 4개 탭 기준)

로그인 후 요청인 앱은 **`소식지` · `분석`(기본 탭) · `채팅` · `내 정보`** 4개 탭을 제공한다.

1. 회원가입 후 프로필 저장을 완료하거나 기존 계정으로 로그인한다.
2. **소식지 탭**: `GET /support-programs`로 사용자 거주 지역 + 전국 주거 지원 사업을 조회한다. 마감 공고는 `마감` 배지·흐림 처리와 하단 정렬로 표시하고, 카드 클릭 시 `GET /support-programs/{program_id}` 상세 요약과 외부 원문 URL을 연다. *(백엔드 구현 완료, 모바일 화면 후속)*
3. **분석 탭**: `POST /records`로 기록을 만들고, 한 화면에서 사진 1~2장(1장 필수) + 위치 + 재질 + 선택 증상 메모를 입력해 `POST /records/{record_id}/analyze`를 호출한다. 현재 서버는 실제 사진/LLM 호출 없이 입력값 기반 샘플 결과를 저장·반환하며 `source=sample`로 표시한다(실제 모델 연동은 후속).
4. **분석 결과 페이지**: 심각도(`0~100%` 또는 `판단 보류`), `추정 원인`(AI 추정 안내·미확인 정보 포함), `해결방안`, `재발 방지책`을 확인한다.
   - `자가`가 아닌 거주 형태라면 필요 시 `POST /records/{record_id}/drafts/landlord`로 임대인 점검 요청문을 생성·복사한다.
   - 업체 상담이 필요하면 `GET /providers`로 업체를 조회한 뒤 실제 업체의 `채팅하기`로 `POST /chat/rooms`를 호출해 1:1 채팅방을 열고 하자 분석 요약을 자동 공유한다.
5. **채팅 탭**: `GET /chat/rooms`로 채팅 목록을 보고 `GET/POST /chat/rooms/{room_id}/messages`로 대화를 이어간다.
6. **내 정보 탭**: `GET/PUT /me/profile`로 프로필을 조회·수정하고, `GET /records`로 내 하자 분석 기록 목록을 불러와 과거 기록의 결과 페이지를 다시 연다.

## 내 정보와 하자 분석 기록 목록 (`GET /records`, 구현 완료)

`내 정보` 페이지의 **내 하자 분석 기록 목록**을 조회한다. 본인이 소유한 기록만 `updated_at` 내림차순(같으면 `created_at`, `id` 내림차순)으로 반환한다.

- 응답은 배열이며 항목 필드는 `record_id`, `location`, `material`, `symptoms`, `suspected_types`(예: `["곰팡이"]`), `severity_score`, `severity_level`, `created_at`, `updated_at`이다.
- 전체 진단·입력 버전·대화는 포함하지 않는다. 진단이 없으면 `suspected_types=[]`, `severity_score=null`, `severity_level=null`이다.
- 목록에서 항목을 선택하면 기존 `GET /records/{record_id}`로 전체 상세를 불러와 분석 결과 페이지를 다시 표시한다.
- 다른 사용자의 기록은 목록에 포함하지 않는다.

## 일괄 분석과 진단 (`POST /records/{record_id}/analyze`, 샘플 구현 완료)

분석 페이지에서 채팅 없이 사진(1~2장)과 위치·재질·선택 증상 메모를 한 번에 제출한다. 2026년 11월 20일 MVP 흐름에 맞춰 현재는 실제 YOLO·비전 LLM·텍스트 LLM을 호출하지 않고, 입력값만 사용한 **결정적 샘플 결과**를 저장·반환한다. 응답의 `source`와 진단의 `source`는 `sample`이다.

- **요청 (`multipart/form-data`)**:
  - `photos`: 이미지 파일 1~2장 (첫 번째 필수, 두 번째 선택)
  - `photo_roles`: 각 사진의 역할 (`overview` | `closeup`). 사진 수와 같아야 하며 서로 달라야 한다.
  - `external_analysis_consent`: 외부 비전 분석 전송 동의 여부 (`boolean`). 샘플 모드에서는 실제 외부 전송을 하지 않는다.
  - `location`: 하자 발견 위치 (필수 문자열, 공백만 불가)
  - `material`: 표면 재질 (필수 문자열, 공백만 불가)
  - `symptoms`: 선택 증상 메모 (`string | null`)
  - 파일은 JPEG·PNG·HEIC·HEIF, 한 장당 10MB 이하만 허용한다. 업로드 파일은 성공·실패 모두 닫고 원본을 저장하지 않는다.
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
        "detections": []
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

- **샘플 모드의 의미**: 실제 사진 분석을 하지 않았으므로 `photo_analysis.applied=false`, 사진 상태 `not_analyzed`, `detections=[]`다. 탐지 좌표·신뢰도·bbox는 만들지 않는다. 관찰 요약·심각도·원인은 입력값만 사용한 참고용 샘플이며, 응답의 `source`, 진단의 `source`, 화면 안내로 실제 분석이 아님을 표시한다.
- **입력과 버전**: 제출한 `location`·`material`·`symptoms`가 실제로 달라지면 `input_revision`을 1 올리고 `diagnosis_generation`을 증가시킨다. 같은 입력이면 버전은 유지하고 생성 번호만 증가한다. 분석 중 다른 입력 변경이 발생하면 아무것도 저장하지 않고 `409`(`revision_conflict`)와 현재 `input_revision`을 반환한다. 사진 원본·좌표·신뢰도는 DB·로그에 저장하지 않는다.
- **정보 부족 시 판단 보류**: 실제 모델 연동 후 사진과 입력만으로 심각도를 가늠하기 어렵다면 `severity_score=null`, `severity_level="undetermined"`를 반환할 수 있다. 현재 샘플은 입력값 기준 참고 수치를 사용한다.
- **명시적 진단 재생성**: `POST /records/{record_id}/diagnosis?regenerate=true`는 후속 구현이다. 현재 분석 결과는 `GET /records/{record_id}`의 `diagnosis`에서 재조회한다.

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

`GET /support-programs`는 로그인 사용자의 프로필 `region_id`와 `housing_type`을 기준으로, 해당 지역·상위 지역(예: 용인시 → 경기도)·전국 공고를 반환한다. 별도 `region_id` 쿼리로 다른 지역을 조회하지 않는다.

- `status=all`(기본)은 마감 공고를 포함하고, `status=active`는 마감되지 않은 공고만 반환한다.
- 정렬: **진행 중(`is_closed=false`) 먼저 → 거주 형태 태그 일치(`housing_type_matched=true`) 우선 → 확정 마감일이 이른 순 → 출처 확인 시각 최신순**. 마감 공고는 하단에 배치한다.
- `housing_type_matched`는 사용자의 거주 형태가 공고 태그와 겹치는지만 표시한다. 태그 일치는 실제 신청 자격을 확정하지 않는다.
- 검증 시드와 같은 제목(끝의 `사업` 제외)·기관·지역의 보조금24 API 행은 목록에서 시드로 대체해 중복 표시하지 않는다. API 행 자체는 상세 ID로 조회할 수 있다.
- `deadline_kind`로 신청기한 상태를 구분한다.
  - `fixed`: 명확히 해석한 날짜가 있고 `deadline_date`가 채워짐
  - `always_open`: 공식 원문이 상시·연중 신청임
  - `unknown`: 원문이 없거나 복수 날짜·범위·조건부 등으로 모호함
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

## 업체 조회 (`GET /regions`, `GET /work-types`, `GET /providers` 구현 완료)

`GET /regions`는 회원 프로필의 거주 지역 선택과 소식지·업체 검색에 사용할 지역 ID와 시·군·구가 포함된 표시 이름을 반환한다. 응답은 `{ "region_id", "name", "display_name" }` 배열이며 `display_name` 순으로 정렬한다. 마이그레이션 `007_profiles_and_regions.sql`은 시연 지역 `용인`(`name="yongin"`, `display_name="경기도 용인시"`)을 시드하고, `008_support_programs.sql`은 상위 지역 `경기도`(`name="gyeonggi"`)를 추가해 용인시의 상위 지역으로 연결한다.

`GET /work-types`는 작업 ID와 이름을 `{ "work_type_id", "name" }` 배열로 반환한다. `010_chat_and_provider_accounts.sql`이 `곰팡이 제거`, `균열 보수`, `벽지·도장 보수`, `원인 점검`을 시드한다. 앱은 진단의 추천 작업을 미리 선택할 수 있다.

업체 검색 전 앱은 등록 주소·거주 지역이 맞는지 확인하고 확인한 거주 지역 ID를 사용한다. `GET /providers?region_id=<UUID>&work_type_id=<UUID>`는 출장 가능 지역과 작업이 **모두** 맞는 업체를 반환한다.

응답 예시 (`200 OK`, 실제 후보):

```json
{
  "providers": [
    {
      "provider_id": "<provider UUID>",
      "name": "용인 곰팡이 수리",
      "phone": "031-000-0000",
      "chat_available": true,
      "is_sample": false
    }
  ],
  "is_sample": false
}
```

실제 후보가 없을 때의 응답 예시 (`200 OK`):

```json
{
  "providers": [
    {
      "provider_id": "00000000-0000-4000-8000-000000000001",
      "name": "시연용 샘플 업체 (곰팡이·결로)",
      "phone": null,
      "chat_available": false,
      "is_sample": true
    }
  ],
  "is_sample": true
}
```

- `chat_available`은 사전 등록된 업체 계정(`providers.account_user_id`)이 연결되어 앱 내 채팅이 가능한지 여부다. 공개 전화번호만 있고 계정이 없는 업체는 `false`다.
- 실제 후보가 하나라도 있으면 `is_sample=false`이고 샘플을 섞지 않는다. 샘플은 전화번호를 만들지 않으며 `chat_available`은 항상 `false`다.
- 등록되지 않은 지역·작업 ID는 `422`, DB 오류는 `500`이다. DB 오류를 빈 목록이나 샘플로 대체하지 않는다.
- 실제 업체·연락처·출장 지역·작업 데이터는 팀이 확인한 자료가 없어 시드하지 않았다. 앱은 `is_sample=true`일 때 시연 안내를 표시한다.

## 업체–요청인 1:1 채팅 (`/chat/*`, 구현 완료)

방 생성·목록·이력 조회·메시지 저장은 FastAPI REST API로 구현했다. 실시간 수신 방식(WebSocket·Supabase Realtime)과 읽음 표시·푸시 알림은 팀 합의 전이라 구현하지 않았다.

| API | 동작 |
| --- | --- |
| `GET /chat/rooms` | 로그인한 요청인 또는 업체 계정이 참여 중인 방을 `last_message_at` 내림차순(없으면 `created_at`)으로 반환한다. 상대방 이름 `counterpart_name`, 최근 메시지 앞 80자 `last_message_preview`, `latest_record_id`를 포함한다. |
| `POST /chat/rooms` | 요청인이 `{ "provider_id": "<UUID>", "record_id": "<UUID>?" }`를 보내 방을 생성하거나 재사용한다. `record_id`가 있으면 서버가 만든 하자 요약을 `record_summary` 메시지로 공유한다. |
| `GET /chat/rooms/{room_id}/messages` | 참여자만 조회한다. `created_at`, `id` 오름차순이며 `limit`(기본 50, 최대 100)·`offset`으로 나눈다. |
| `POST /chat/rooms/{room_id}/messages` | 참여자가 `{ "client_message_id": "<UUID>", "content": "..." }`를 보내 저장한다. 발신자·역할은 토큰과 방 참여 정보로 정한다. |

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
- **반복 조회(폴링) 계약**: 앱은 `GET /chat/rooms`로 `last_message_at` 변화를 확인하고, `GET /chat/rooms/{room_id}/messages?limit=50&offset=<받은 개수>`로 새 메시지를 가져온다. `has_more=true`면 `offset + limit`으로 이어서 조회한다. 서버 푸시·WebSocket은 제공하지 않는다.
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
- 채팅 실시간 수신 방식(`REST 폴링` / `WebSocket` / `Supabase Realtime`)과 읽음 표시·푸시 알림
- 보조금24 API(`gov24/v3/serviceList`) 동기화의 실제 운영 키·응답 최신성 검증과 주거 필터 키워드 보정
