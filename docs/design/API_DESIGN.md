# MVP API 계약 초안

[백엔드 설계](BACKEND_DESIGN.md)와 [DB 설계](DB_DESIGN.md)의 합의를 요청·응답으로 구체화한 초안이다. 경로·필드명은 앱 담당자와 최종 확인할 대상이다. 아래 UUID 값은 문서에서 읽기 쉽도록 자리표시자로 적었다.

## 문서 범위

현재 코드에 구현된 기록 API(`POST /records`, `GET /records/{record_id}`, `PATCH /records/{record_id}`)와 사진·위치·재질 일괄 분석(`POST /records/{record_id}/analyze`)의 계약은 아래 구현 확정 사항과 일괄 분석 섹션을 따른다. 이미 구현된 `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`은 분석 채팅창 제거에 따라 **현재 MVP 미사용(보류/레거시)** 상태이며, 문서 하단에 참고용으로 분리했다.

회원 프로필, 소식지, 실제 모델 기반 일괄 분석·진단, 내 기록 목록, 요청문 생성, 업체 검색과 1:1 채팅 경로는 2026년 11월 20일 변경 사항을 반영한 후속 구현 설계다. 실행과 호출 절차는 [README](../../README.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `POST /records`는 201과 `record_id`, `input_revision`(최초 0)을 반환한다.
- `GET /records/{record_id}`는 저장된 입력(`location`, `material`, `symptoms`, `photo_observations`)과 `diagnosis`, `drafts`의 생성 당시 버전 및 `is_current`를 반환한다. *(구현본에는 레거시 `questions`, `messages`, `next_question` 필드도 함께 포함된다.)*
- `PATCH /records/{record_id}`는 `location`·`material`·`symptoms`를 받고 `input_revision`을 요구하지 않는다. 실제 값이 바뀔 때만 버전을 올리며, 명시한 `null`은 값을 지운다.
- `POST /records/{record_id}/analyze`는 사진 1~2장과 위치·재질·증상·외부 분석 동의를 multipart로 받아 입력값 기반 샘플 진단을 저장한다. 자세한 계약은 아래 일괄 분석 섹션을 따른다.
- 공통 오류 형식은 `{ "code", "message", "input_revision"? }`이다. 처리하지 못한 서버·DB 오류는 내용을 노출하지 않고 500 `internal_error`로 반환한다.
- *(MVP 미사용/보류)* `POST/PUT /records/{record_id}/messages`와 `POST /records/{record_id}/next-question`의 구현 확정 사항은 문서 하단 레거시 섹션에 유지한다.

## 회원가입과 프로필 (구현 예정)

일반 회원가입은 `요청인` 전용이다. 앱에서 Supabase Auth로 **이메일·비밀번호** 계정을 만들고, 회원가입 과정에서 `닉네임`, `거주 지역`(필수), `등록 주소`(선택), `거주 형태`(`월세`, `전세`, `반전세`, `자가`, `기타`)를 입력받는다. 인증 가능한 세션을 얻은 뒤 FastAPI에 프로필을 저장한다. 이메일 확인이 필요한 환경은 확인 후 동일 계정으로 프로필 등록을 완료한다. 계정 생성 후 프로필 저장에 실패하면 프로필 저장만 재시도한다. 시연용 `업체` 계정은 Supabase Auth와 `profiles`(`role="provider"`)에 사전 등록한다.

| API | 동작 |
| --- | --- |
| `GET /me/profile` | 인증된 본인의 `nickname`, `role`, `region_id`, `address`, `housing_type`을 조회한다. 미등록이면 프로필이 없음을 반환(`404`)해 등록 화면으로 이어간다. |
| `PUT /me/profile` | `nickname`, `region_id`, `address`(선택/null 가능), `housing_type`을 받아 인증된 본인의 프로필을 등록·수정한다. `user_id`는 토큰에서 결정하고 `role`은 클라이언트가 변경할 수 없다. |

`housing_type` 허용값은 `monthly_rent`(월세), `jeonse`(전세), `semi_jeonse`(반전세), `owned`(자가), `other`(기타)다.

주소·지역이 필요한 화면(임대인 점검 요청, 업체 찾기)에서 앱은 등록 주소와 거주 지역을 보여주고 맞는지 확인한다. 다르면 위 프로필 저장 API로 수정한 뒤 사용한다. 프로필 미등록 상태에서도 기존 계정의 로그인과 기록 조회는 가능하며, 프로필이 필요한 행동에서 등록을 안내한다.

소식지와 업체 검색에는 확인한 `region_id`를 보낸다. 임대인 점검 요청문에 상세 주소가 필요하면 앱에서 생성된 초안에 확인한 주소를 반영한다. 상세 `address`는 진단·요청문 생성 API의 모델 입력에 자동으로 포함하지 않는다. 요청문 편집본 저장 API는 추가하지 않는다.

## 인증과 버전

로그인 후 앱은 FastAPI 요청에 `Authorization: Bearer <access_token>`을 보낸다. 모든 API(`GET /health` 제외)는 인증을 확인하고, 기록·채팅 API는 소유권 또는 참여 권한을 확인한다. 사용자 ID는 검증한 토큰(`sub`)에서 결정한다.

`input_revision`은 기록 입력의 버전이다. 입력(`location`, `material`, `symptoms`, `photo_observations`) 변경은 버전 증가와 함께 원자적으로 처리하고, 생성 결과는 사용한 입력 버전이 현재 버전과 일치할 때 저장한다. 버전 충돌은 `409`로 반환한다.

## 기본 순서 (요청인 앱 4개 탭 기준)

로그인 후 요청인 앱은 **`소식지` · `분석`(기본 탭) · `채팅` · `내 정보`** 4개 탭을 제공한다.

1. 회원가입 후 프로필 저장을 완료하거나 기존 계정으로 로그인한다.
2. **소식지 탭**: `GET /support-programs`로 사용자 거주 지역 + 전국 주거 지원 사업을 조회한다. 마감 공고는 `마감` 배지·흐림 처리와 하단 정렬로 표시하고, 카드 클릭 시 `GET /support-programs/{program_id}` 상세 요약과 외부 원문 URL을 연다.
3. **분석 탭**: `POST /records`로 기록을 만들고, 한 화면에서 사진 1~2장(1장 필수) + 위치 + 재질 + 선택 증상 메모를 입력해 `POST /records/{record_id}/analyze`를 호출한다. 현재 서버는 실제 사진/LLM 호출 없이 입력값 기반 샘플 결과를 저장·반환하며 `source=sample`로 표시한다(실제 모델 연동은 후속).
4. **분석 결과 페이지**: 심각도(`0~100%` 또는 `판단 보류`), `추정 원인`(AI 추정 안내·미확인 정보 포함), `해결방안`, `재발 방지책`을 확인한다.
   - `자가`가 아닌 거주 형태라면 필요 시 `POST /records/{record_id}/drafts/landlord`로 임대인 점검 요청문을 생성·복사한다.
   - 업체 상담이 필요하면 `GET /providers`로 업체를 조회한 뒤 실제 업체의 `채팅하기`로 `POST /chat/rooms`를 호출해 1:1 채팅방을 열고 하자 분석 요약을 자동 공유한다.
5. **채팅 탭**: `GET /chat/rooms`로 채팅 목록을 보고 `GET/POST /chat/rooms/{room_id}/messages`로 대화를 이어간다.
6. **내 정보 탭**: `GET/PUT /me/profile`로 프로필을 조회·수정하고, `GET /records`로 내 하자 분석 기록 목록을 불러와 과거 기록의 결과 페이지를 다시 연다.

## 내 정보와 하자 분석 기록 목록 (`GET /records`, 구현 예정)

`내 정보` 페이지의 **내 하자 분석 기록 목록**을 조회한다. 본인이 소유한 기록만 `updated_at` 내림차순으로 반환한다.

- 항목 필드: `record_id`, `location`, `material`, `symptoms`, `suspected_types`(예: `["곰팡이"]`), `severity_score`, `severity_level`, `updated_at`.
- 목록에서 항목을 선택하면 기존 `GET /records/{record_id}`로 전체 상세를 불러와 분석 결과 페이지를 다시 표시한다.

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

## 요청문 (`landlord`, `provider`, 구현 예정)

요청문 종류는 `landlord`(임대인 점검 요청문) 또는 `provider`(업체 견적 요청문)로 구분한다.

| API | 동작 |
| --- | --- |
| `POST /records/{record_id}/drafts/{kind}` | 현재 입력과 진단을 바탕으로 생성한다. 입력 버전과 진단 생성 번호가 모두 현재 값과 일치하는 요청문이 있으면 재사용한다. |
| `POST /records/{record_id}/drafts/{kind}?regenerate=true` | 새로 생성하며 성공했을 때 최신본을 교체한다. |
| `GET /records/{record_id}/drafts/{kind}/template` | 현재 입력의 확인된 사실(위치·재질·증상·심각도)을 채운 기본 양식을 반환한다. 모델을 호출하지 않는다. |

요청문 생성 응답은 `text`, `input_revision`, 생성에 사용한 `diagnosis_generation`을 담는다. `자가` 거주 형태(`housing_type="owned"`)인 요청인에게는 앱 UI에서 `landlord` 요청문 버튼을 기본 숨김 처리한다. `provider` 견적 요청문은 업체 채팅 입력창의 첫 문의 초안·복사 용도로 재활용한다.

진단 재생성 성공 시 이전 요청문의 복사를 막고 새 진단으로 다시 생성한다. 요청문 생성 중 진단이 교체되면 저장 없이 `409`를 반환한다. 사용자가 편집한 문구는 앱 화면에서 유지하며 저장 API로 보내지 않는다.

## 소식지 조회 (`GET /support-programs`, 구현 예정)

- `GET /support-programs?region_id=<UUID>&status=<all|active>`:
  - `region_id`가 생략되면 로그인한 사용자의 프로필 `region_id`를 사용한다.
  - 해당 지자체(`region_scope="local"`) 사업과 전국(`region_scope="national"`) 사업을 함께 반환하며, `status=active`이면 마감 공고를 제외하고 기본(`all`)이면 전체를 반환한다.
  - 정렬 순서: **진행중(`is_closed=false`) 먼저 + 사용자 `housing_type` 일치 사업 우선 → 마감(`is_closed=true`) 하단 배치**.
  - 항목 필드: `id`, `title`, `summary`, `organization_name`, `region_scope`, `region_name`, `target_housing_types`, `housing_type_matched`, `deadline_text`, `deadline_date`, `is_closed`, `source_attribution`, `detail_url`.
- `GET /support-programs/{program_id}`:
  - 소식지 상세 요약 페이지에 필요한 지원 내용, 선정 기준·대상 거주 형태, 신청기한(`deadline_text`, `is_closed`), `apply_method`, `detail_url`(외부 브라우저 열기용), `source_attribution`을 반환한다.

## 업체 조회 (`GET /regions`, `GET /work-types`, `GET /providers`, 구현 예정)

`GET /regions`는 회원 프로필의 거주 지역 선택과 소식지·업체 검색에 사용할 지역 ID와 시·군·구가 포함된 표시 이름을 반환한다. `GET /work-types`는 작업 ID와 이름을 반환한다. 앱은 진단의 추천 작업을 미리 선택한다.

업체 검색 전 앱은 등록 주소·거주 지역이 맞는지 확인하고 확인한 거주 지역 ID를 사용한다. `GET /providers?region_id=<UUID>&work_type_id=<UUID>`는 출장 가능 지역과 작업이 모두 맞는 업체를 반환한다.

- 응답에는 후보 목록과 `is_sample`을 담는다. 각 업체 항목에는 `provider_id`, `name`, `phone`, `chat_available`(`boolean`), `is_sample`을 포함한다.
- 검색이 성공했고 실제 후보가 없을 때만 샘플을 반환한다. 실제 업체 카드의 주 버튼은 `채팅하기`, 보조 버튼은 `전화하기`이며, `샘플` 업체 연락 버튼은 시연 안내를 표시한다.

## 업체–요청인 1:1 채팅 (`/chat/*`, 구현 예정)

기본 방 생성·이력 조회·메시지 저장은 FastAPI REST API로 정의한다. **실시간 메시지 수신 방식(FastAPI REST 폴링 vs FastAPI WebSocket vs Supabase Realtime)과 시연용 업체 계정 화면 세부 구성은 팀원 협의 후 확정(보류)**한다.

| API | 동작 |
| --- | --- |
| `GET /chat/rooms` | 로그인한 요청인 또는 업체 계정이 참여 중인 채팅방 목록을 `last_message_at` 내림차순으로 조회한다. 상대방 이름, 최근 메시지 미리보기, 최근 연결 기록 요약을 포함한다. |
| `POST /chat/rooms` | 요청인이 `{ "provider_id": "<UUID>", "record_id": "<UUID>?" }`를 보내 `(requester_id, provider_id)` 채팅방을 생성하거나 기존 방을 반환한다. `record_id`가 전달되면 해당 기록의 하자 요약(`record_summary`) 메시지를 자동 등록한다(직전 메시지와 동일 기록 요약이면 중복 방지). |
| `GET /chat/rooms/{room_id}/messages` | 참여자 권한을 확인한 뒤 채팅방의 메시지 목록을 시간순으로 반환한다. (`since` 등 증분 조회 파라미터는 전송 방식 확정 시 추가) |
| `POST /chat/rooms/{room_id}/messages` | `{ "client_message_id": "<UUID>", "content": "..." }`를 받아 참여자 확인 및 멱등성 검사 후 메시지를 저장하고 반환한다. |

- `샘플` 업체(`is_sample=true`)는 DB에 실제 업체·계정이 없으므로 `POST /chat/rooms`를 호출하지 않고 앱에서 시연 안내를 띄운다.

## 오류 응답 초안

오류는 `code`와 사용자에게 보여줄 `message`를 포함한다. 버전 충돌 시 현재 입력 버전도 제공한다.

| 상황 | 상태 코드 |
| --- | --- |
| 인증 실패 또는 만료 | 401 |
| 기록·프로필·지원 사업·채팅방을 찾지 못했거나 접근 권한 없음 | 404 |
| 입력 버전 충돌, 진단 교체 충돌, 동일 메시지 ID의 내용 충돌 | 409 |
| 요청 필드·거주 형태·검색 코드·업로드 파일이 유효하지 않음 | 422 |
| 외부 모델 또는 공공 API 호출·응답 형식 오류 | 502 |
| 외부 모델 또는 공공 API 응답 제한 시간 초과 | 504 |

일괄 분석 내 사진별 분석 성공·실패는 분석 응답의 `photo_analysis` 안에서 구분한다. 전체 요청 처리 실패는 오류 응답으로 반환한다. 진단·요청문 생성 실패 시 기존 입력과 유효 결과를 유지한다. 진단 생성 실패는 정보 부족에 따른 판단 보류(`severity_score=null`)와 구분한다.

## 기존 구현 · MVP 미사용(보류): AI 추가 질문 대화 API

아래 엔드포인트는 현재 저장소(`apps/api/app/records.py`, `apps/api/app/sample_questions.py`)에 구현·테스트되어 있으나, 분석 페이지 채팅창 제거 결정에 따라 **현재 MVP 흐름에서는 호출하지 않는다**. 추후 설문/객관식 추가 질문을 도입하기로 결정할 경우 참고·재사용하기 위해 기존 확정 계약을 기록해 둔다.

- **`POST /records/{record_id}/messages`**: `client_message_id`, `question_id?`, `selected_option_id` 또는 `content`, `input_revision`을 받아 사용자 메시지를 저장하고 `input_revision`을 1 올린다. `(record_id, client_message_id)` 멱등성 및 내용 충돌 시 409(`message_conflict`)를 반환한다.
- **`PUT /records/{record_id}/messages/{message_id}`**: `content`, `input_revision`을 받아 과거 사용자 메시지를 수정한다. 내용이 다르면 이후 대화·질문을 삭제하고 `input_revision`을 올린다.
- **`POST /records/{record_id}/next-question`**: 요청 본문 없이 현재 기록과 대화를 읽어 `sample_questions.py`의 시연 규칙(`source="sample"`, 창가 얼룩 2문항: `recurred`·`wiped`)을 반환하고 `next_question_result`에 캐시한다.

## 남은 연동 확인

- 실제 모델 연동 시 `POST /records/{record_id}/analyze`의 YOLO·비전 LLM·텍스트 LLM 인증·요청·응답·좌표 형식과 배포 환경 제한 시간
- 채팅 실시간 수신 방식(`REST 폴링` / `WebSocket` / `Supabase Realtime`)과 `GET /chat/rooms/{room_id}/messages` 증분 조회 파라미터
- 보조금24 API(`gov24/v3/serviceList`) 연동 시 주거 필터 키워드 및 동기화 주기
