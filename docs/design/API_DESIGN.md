# MVP API 계약 초안

[백엔드 설계](BACKEND_DESIGN.md)와 [DB 설계](DB_DESIGN.md)의 합의를 요청·응답으로 구체화한 초안이다. 경로·필드명은 앱 담당자와 최종 확인할 대상이다. 아래 UUID 값은 문서에서 읽기 쉽도록 자리표시자로 적었다.

## 문서 범위

현재 구현된 기록·메시지 API의 계약은 아래 구현 확정 사항을 따른다. 사진 분석, 질문·진단·요청문 생성, 업체 검색 경로는 후속 구현을 위한 설계다. 실행과 호출 절차는 [README](../../README.md)를 따른다.

## 구현 확정 사항

2026년 11월 19일 MVP 구현에서 아래를 확정했다.

- `POST /records`는 201과 `record_id`, `input_revision`(최초 0)을 반환한다.
- `GET /records/{record_id}`는 `questions`와 `messages`를 각각 `sequence` 순으로 반환한다. 두 테이블은 기록별 공용 순번(`records.conversation_sequence`)을 함께 사용하므로 두 배열을 합쳐 정렬하면 대화 순서가 유지된다. `diagnosis`, `next_question`, `drafts`에는 생성 당시 버전과 `is_current`를 포함한다.
- `PATCH /records/{record_id}`는 `location`·`symptoms`만 받고 `input_revision`을 요구하지 않는다. 실제 값이 바뀔 때만 버전을 올리며, 명시한 `null`은 값을 지운다.
- 메시지 저장 응답은 `{ "message": {...}, "input_revision": <현재 기록 버전> }`이다. 재전송 시 `message`는 기존 메시지의 현재 저장본이고 `input_revision`은 현재 기록 버전이다. PUT으로 편집된 내용은 되돌리지 않는다.
- 재전송 확인은 기록 소유권 확인 뒤, 버전 검사 전에 한다. 같은 `client_message_id`에 내용·질문·선택지가 다르면 409다.
- `PUT`은 기록 소유권 확인 → `input_revision` 검사 → 수정 대상 메시지 조회 순서로 처리한다. 오래된 버전이면 대상 메시지가 없어도 최신 버전을 포함한 409를 반환하고, 버전이 일치할 때 대상이 없으면 404다. 내용이 같으면 삭제·버전 증가 없이 200을 반환하고, 내용이 다르면 그 `sequence`보다 뒤의 메시지·질문을 삭제하고 버전을 올린다.
- 다른 기록의 질문, 없는 질문은 404다. 질문은 있지만 없는 선택지를 보내면 422다. 없는 메시지, 다른 사용자 메시지, `assistant` 메시지 수정은 404다.
- 공통 오류 형식은 `{ "code", "message", "input_revision"? }`이다. 처리하지 못한 서버·DB 오류는 내용을 노출하지 않고 500 `internal_error`로 반환한다.

## 인증과 버전

로그인 후 앱은 FastAPI 요청에 `Authorization: Bearer <access_token>`을 보낸다. 모든 API는 인증을 확인하고, 기록 관련 API는 기록 소유권을 확인한다. 소유자 ID는 검증한 토큰에서 결정한다.

`input_revision`은 기록 입력의 버전이다. 사용자 메시지 저장과 수정은 앱이 확인한 버전을 보낸다. 입력 변경은 버전 증가와 함께 원자적으로 처리하고, 생성 결과는 사용한 입력 버전이 현재 버전과 일치할 때 저장한다. 버전 충돌은 `409`로 반환한다.

## 기본 순서

1. `POST /records`로 기록을 만든다.
2. 사진 선택 후 `POST /records/{record_id}/photo-analysis`에 사진 한 장 또는 두 장을 함께 보낸다. 분석 상태와 관찰 결과를 받는다.
3. `POST /records/{record_id}/next-question`으로 첫 질문을 받는다.
4. `POST /records/{record_id}/messages`로 사용자 답변을 저장한다.
5. `POST /records/{record_id}/next-question`으로 AI 응답과 필요한 질문을 받는다. 이미 저장된 같은 입력 버전의 응답은 재사용한다.
6. 추가 질문이 없거나 사용자가 현재 정보로 결과 보기를 선택하면 `POST /records/{record_id}/diagnosis`를 호출한다.
7. 필요에 따라 요청문을 생성하거나 업체를 검색한다.

분석에서 사용할 결과가 없으면 `PATCH /records/{record_id}`로 위치와 증상을 저장하고 질문을 진행한다.

## 선택지와 사용자 메시지

질문 응답에는 다음 정보를 담는다.

```json
{
  "input_revision": 1,
  "reply": null,
  "question": {
    "id": "<question UUID>",
    "content": "닦은 뒤 같은 흔적이 다시 생겼나요?",
    "options": [
      { "id": "recurred", "label": "다시 생겼어요" },
      { "id": "first_seen", "label": "처음 발견했어요" },
      { "id": "unknown", "label": "잘 모르겠어요" }
    ]
  },
  "ready_for_diagnosis": false
}
```

질문은 한 번에 하나를 반환한다. 질문이 필요 없으면 `question`은 null이고 `ready_for_diagnosis`는 true다. 선택지가 없는 질문에는 빈 배열을 반환한다. 자유 입력에 대한 AI의 짧은 반응은 `reply`에 담는다. 서버는 종료 상태를 포함한 성공 응답 전체를 입력 버전과 함께 저장한다. 응답이 유실되어 재요청하면 같은 버전의 저장 응답을 반환하며, 질문이나 응답이 모두 null이어도 추가 모델 호출을 하지 않는다. 실패한 호출은 성공 응답으로 저장하지 않는다.

선택 버튼을 누르면 다음 요청을 보낸다.

```json
{
  "client_message_id": "<client UUID>",
  "question_id": "<question UUID>",
  "selected_option_id": "recurred",
  "input_revision": 1
}
```

직접 입력이면 `selected_option_id` 대신 `content`를 보낸다. 서버는 둘 중 정확히 하나만 받는다. 선택지 ID는 해당 질문에 속하는지 확인하고, 저장된 표시 문구를 사용자 메시지로 저장한다. 직접 입력 메시지도 같은 저장 구조를 사용한다.

저장 응답에는 메시지 ID, 저장한 문구, 순서, 변경된 `input_revision`을 포함한다. 같은 `client_message_id`와 같은 요청을 다시 보내면 기존 메시지를 반환한다. 다른 내용이면 `409`로 거부한다.

재전송은 최초 POST의 `question_id`, `selected_option_id`, 직접 입력 `content`를 비교하며 `input_revision`은 비교에서 제외한다. 같은 label의 다른 선택지와 선택 답변·직접 입력도 구분한다. 최초 선택지 ID와 직접 입력은 응답에 노출하지 않는 내부 컬럼에 보존하고 PUT으로 변경하지 않는다. 마이그레이션 이전 메시지는 최초 제출 방식을 복원할 수 없어 같은 ID의 POST에 409 `message_conflict`를 반환한다. 앱은 기록을 다시 조회해 현재 메시지를 확인한다.

과거 메시지 수정은 `PUT /records/{record_id}/messages/{message_id}`에 새 `content`와 편집 시작 시 확인한 `input_revision`을 보낸다. 앱은 후속 대화 삭제 경고를 먼저 보여준다. 실제 변경 시 이후 메시지와 질문을 삭제하고 결과를 이전 입력의 결과로 취급한다.

## 진단과 요청문

진단 응답은 결과에 사용한 `input_revision`, `diagnosis_generation`과 `diagnosis`를 담는다. 진단 JSON의 필드와 허용값은 백엔드 설계의 진단 응답 표를 따른다. 기본 생성 요청은 현재 버전 결과를 재사용한다. `regenerate=true`일 때 새로 생성한다.

요청문 종류는 `landlord` 또는 `provider`로 구분한다.

| API | 동작 |
| --- | --- |
| `POST /records/{record_id}/drafts/{kind}` | 현재 입력과 진단을 바탕으로 생성한다. 입력 버전과 진단 생성 번호가 모두 현재 값과 일치하는 요청문이 있으면 반환한다. |
| `POST /records/{record_id}/drafts/{kind}?regenerate=true` | 새로 생성하며 성공했을 때 최신본을 교체한다. |
| `GET /records/{record_id}/drafts/{kind}/template` | 현재 입력의 확인된 사실을 채운 기본 양식을 반환한다. 모델을 호출하지 않는다. |

요청문 생성 응답은 `text`, `input_revision`, 생성에 사용한 `diagnosis_generation`을 담는다. 기본 양식은 현재 입력만 사용하므로 진단 생성 번호를 요구하지 않는다. 진단 재생성 성공 시 이전 요청문의 복사를 막고 새 진단으로 다시 생성한다. 요청문 생성 중 진단이 교체되면 저장 없이 `409`를 반환한다. 사용자가 편집한 문구는 앱 화면에서 유지하며 저장 API로 보내지 않는다.

## 업체 조회

`GET /regions`는 지역 ID와 시·군·구가 포함된 표시 이름을 반환한다. `GET /work-types`는 작업 ID와 이름을 반환한다. 앱은 진단의 추천 작업을 미리 선택한다.

`GET /providers?region_id=<UUID>&work_type_id=<UUID>`는 출장 가능 지역과 작업이 모두 맞는 업체를 반환한다. 응답에는 후보 목록과 `is_sample`을 담는다. 업체에는 업체명과 연락처를 포함한다. 검색이 성공했고 실제 후보가 없을 때만 샘플을 반환한다. 샘플 연락 버튼은 시연 안내를 표시한다.

## 오류 응답 초안

오류는 `code`와 사용자에게 보여줄 `message`를 포함한다. 버전 충돌 시 현재 입력 버전도 제공한다.

| 상황 | 상태 코드 |
| --- | --- |
| 인증 실패 또는 만료 | 401 |
| 기록이나 질문·메시지를 찾지 못했거나 다른 사용자 소유 | 404 |
| 입력 버전 충돌 또는 동일 메시지 ID의 내용 충돌 | 409 |
| 요청 필드·선택지·검색 코드가 유효하지 않음 | 422 |
| 외부 모델 호출·응답 형식 오류 | 502 |
| 외부 모델 응답 제한 시간 초과 | 504 |

사진별 분석 성공·실패는 분석 응답 안에서 구분한다. 전체 요청 처리 실패는 오류 응답으로 반환한다. 질문과 요청문 생성 실패 시 기존 입력과 결과를 유지한다. 진단 생성 실패는 정보 부족에 따른 판단 보류와 구분한다.

## 남은 연동 확인

사진별 역할과 임시 표시 좌표를 포함하는 multipart 세부 필드, 업로드 크기·파일 형식 제한, 모델·배포 환경의 제한 시간, YOLO API의 인증과 좌표 형식은 담당자와 확인한 뒤 고정한다.
