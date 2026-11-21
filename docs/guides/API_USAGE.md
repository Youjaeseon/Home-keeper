# API 동작·호출 가이드 및 구현 메모

프로젝트 개요는 [README](../../README.md), 환경 설정과 DB·테스트 절차는 [개발 환경·DB·테스트 가이드](DEVELOPMENT.md), 전체 요청·응답 계약은 [API 설계](../design/API_DESIGN.md)를 확인합니다.

## API 동작

공통 오류 형식:

```json
{ "code": "revision_conflict", "message": "입력이 변경되었어요...", "input_revision": 2 }
```

| 상황 | 상태 |
| --- | --- |
| 인증 없음/서명·만료·발급자·대상 오류 | 401 |
| 없는 기록, 다른 사용자 기록, 없는 질문, 없는 메시지, assistant 메시지 수정, 미등록 프로필, 없는 지원 사업, 비참여자·없는 채팅방, 샘플 업체 채팅 시도 | 404 |
| `input_revision` 충돌, 분석 중 입력 변경, 같은 `client_message_id`의 다른 내용, 진단 미생성, 진단 변경 충돌 | 409 |
| 요청 형식, 없는 선택지, 잘못된 사진 형식·개수·크기·역할, 프로필의 닉네임·지역·거주 형태, 잘못된 소식지 `status`, 미등록 지역·작업, 채팅 불가 업체, 메시지 길이·빈 입력 | 422 |
| 진단·요청문 모델 호출·응답 형식 오류 | 502 |
| 진단·요청문 모델 키 미설정, YOLO만 설정하고 LLM 키가 없는 분석, 사진 분석 의존성 실행 불가 | 503 |
| 진단·요청문 모델 응답 제한 시간 초과 | 504 |
| 예기치 않은 서버/DB 오류(업체 검색 DB 오류 포함) | 500 |

기록의 `input_revision`은 0에서 시작합니다. 위치·재질·증상, 사용자 메시지 추가, 사용자 메시지 내용 수정, 일괄 분석의 입력 변경처럼 실제 입력이 바뀔 때만 1씩 증가합니다. 같은 값을 다시 저장하거나 같은 메시지를 재전송하거나 같은 입력으로 다시 분석하면 증가하지 않습니다. 분석은 성공할 때마다 `diagnosis_generation`을 올립니다.

`GET /records/{record_id}` 응답의 `diagnosis`, `next_question`, `drafts`에는 생성 당시 `input_revision`(과 요청문의 경우 `diagnosis_generation`)과 `is_current`가 들어 있습니다. 입력이 바뀐 뒤에는 `is_current`가 false이므로 앱이 이전 결과임을 표시할 수 있습니다.

질문과 메시지는 `records.conversation_sequence`에서 순서를 함께 발급받습니다. 두 테이블의 `sequence`를 합쳐 정렬하면 기록 안의 대화 순서가 안정적으로 유지됩니다. 과거 사용자 메시지를 수정하면 그 `sequence`보다 큰 메시지와 질문을 같은 트랜잭션에서 삭제합니다.

## 호출 예시

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

## 사진·위치·재질 일괄 분석

`POST /records/{record_id}/analyze`는 multipart/form-data로 사진 1~2장, 사진 역할, 위치, 재질, 선택 증상 메모, 외부 분석 동의 여부(생략 시 `true`)를 받습니다. `YOLO_MODEL_PATH` 설정 시 YOLO 탐지를 수행하고, 동의와 `MODEL_API_KEY`가 있으면 Meta SAM 3.1로 분할합니다. YOLO가 탐지하지 못했거나 실행할 수 없는 사진만 동의와 `LLM_API_KEY`가 있을 때 비전 LLM이 독립 관찰합니다. 두 모델 경로가 모두 미설정이면 샘플 모드입니다. `YOLO_MODEL_PATH`만 켜고 `LLM_API_KEY`가 없으면 `503`(`llm_unavailable`)입니다.

```bash
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/analyze"   -H "Authorization: Bearer $ACCESS_TOKEN"   -F "photos=@/path/to/overview.jpg;type=image/jpeg"   -F "photo_roles=overview"   -F "external_analysis_consent=false"   -F "location=안방 창틀 아래"   -F "material=실리콘"   -F "symptoms=닦아도 검은 얼룩이 다시 생겨요"

curl -s "http://127.0.0.1:8000/records/$RECORD_ID"   -H "Authorization: Bearer $ACCESS_TOKEN"
```

두 장을 보낼 때는 `photos`와 `photo_roles`를 각각 두 번 보내고 역할을 `overview`, `closeup`으로 구분합니다. 사진 수와 역할 수가 같아야 하며 역할은 중복될 수 없습니다. JPEG·PNG·HEIC·HEIF, 한 장당 10MB 이하만 허용합니다.

샘플 모드의 응답과 `GET /records/{record_id}`의 `photo_observations`에는 `source="sample"`, `applied=false`, 사진 상태 `not_analyzed`, `detections=[]`, `vision_observation=null`이 들어갑니다. 탐지 좌표·신뢰도는 만들지 않으며 원본 사진은 DB·로그에 저장하지 않습니다. 진단의 `source`도 `sample`이고, 심각도·추정 원인·해결방안·재발 방지책은 입력값만 사용한 참고용 결과입니다. 입력이 실제로 바뀌면 `input_revision`이 오르고 `diagnosis_generation`이 증가하며, 분석 중 입력이 바뀌면 409를 반환합니다.

실제 사진 분석 시 `photo_analysis.applied=true`이고 사진별 상태는 `analyzed` 또는 `failed`, 출처는 `yolo`, `yolo_sam`, `vision_llm` 중 하나입니다. 사진마다 출처가 섞이면 최상위 `photo_analysis.source`와 응답 `source`가 `yolo_vision_llm`입니다. `detections` 항목은 `object_id`, `class_id`, `label`, `raw_label`, `confidence`, `bbox`(원본 기준 반열린 xyxy), `image_size`([너비, 높이]), `area_ratio`(0~1, 이미지 전체 면적 대비 화면 점유 비율), `source=yolo`, `segmentation_status`, `mask`를 포함합니다. `mask`는 null 또는 `encoding=coco_rle`, `size`([높이, 너비]), `counts`, 시각화용 `svg_path`, 원본 기준 반열린 `bounds`(left/top/right/bottom), `source=sam-3.1`입니다. RLE는 bounds 영역에 맞춰 배치합니다.

라벨은 `crack`→`균열`, `paint_peel`/`peeling`→`벗겨짐`, `mold`/`mould`→`곰팡이`로 정규화하고 원본 클래스명은 `raw_label`에 남깁니다. 미등록 라벨은 원문을 유지합니다. `area_ratio`는 SAM 마스크가 있으면 마스크 픽셀 비율(bounds 스케일 반영), 없으면 bbox 면적 비율입니다.

분할 상태는 `completed`, `no_mask`, `failed`, `unavailable`(키 미설정), `skipped_no_consent`입니다. SAM 실패 시 YOLO 결과는 보존합니다. 사진당 최대 16개를 탐지합니다. 실제 이미지 디코딩 실패 또는 2,500만 픽셀 초과는 `422`입니다. 사진별 비전 LLM 호출 실패·판독 불가는 `status="failed"`로 남기고 전체 분석과 텍스트 진단은 계속합니다. 원본은 저장하지 않으며 외부 전송에는 동의가 필요합니다.

진단 모델이 설정된 경우 저장된 사진 관찰 요약(라벨·신뢰도 %·개수·화면 점유 비율)과 마스킹한 위치·재질·증상, DB 작업 종류로 구조화 진단을 생성합니다. 원시 bbox·COCO RLE·`svg_path`는 전송하지 않습니다. 진단 호출·형식 오류는 `502`, 제한 시간 초과는 `504`이며 기존 결과를 유지합니다.

## 진단 생성·재생성

`POST /records/{record_id}/diagnosis`는 저장된 사진 관찰과 현재 입력으로 진단을 만들거나 기존 진단을 반환합니다.

```bash
# 입력 버전이 같은 기존 진단 재사용(모델 미호출)
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/diagnosis" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 강제 재생성
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/diagnosis?regenerate=true" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

응답은 `{ "record_id", "input_revision", "diagnosis_generation", "diagnosis", "source" }`입니다. `source`는 `llm` 또는 `sample`이며 `diagnosis.source`와 같습니다. 재생성 또는 입력 변경 상태에서 위치·재질이 비어 있으면 `422`, 생성 중 입력이 바뀌면 `409 revision_conflict`, 모델 키 미설정은 기존 진단이 있어도 항상 `503`, 호출·형식 오류는 `502`, 제한 시간 초과는 `504`입니다. 실패해도 기존 진단은 유지됩니다. 판단 보류 시 `severity_score=null`, `severity_level=undetermined`, `suspected_types=[]`, `원인 점검` 작업이 저장됩니다.

모바일은 `apps/mobile/src/app/analyze.tsx`에서 사진 선택·입력·동의를 받아 기록 생성 후 분석을 호출하고, `apps/mobile/src/app/result/[recordId].tsx`에서 저장된 결과를 다시 조회해 표시합니다. `regenerateDiagnosis` 함수가 진단 재생성 API를 호출합니다. FormData 전송 시 `Content-Type`을 직접 지정하지 않아 fetch가 boundary를 설정합니다.

`POST /records/{record_id}/next-question`는 현재 서버의 입력과 대화만 사용하며, 클라이언트가 사용자 ID나 대화 전체를 다시 보내지 않습니다. 질문·선택지는 서버가 `source="sample"`로 표시해 반환합니다. 실제 LLM이 아니라 아래 두 질문을 사용하는 시연 규칙입니다.

## 요청문·업체 검색·1:1 채팅

### 요청문

```bash
# 현재 분석 결과로 임대인 점검 요청문 생성(있으면 재사용)
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/drafts/landlord" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 명시적 재생성
curl -s -X POST "http://127.0.0.1:8000/records/$RECORD_ID/drafts/provider?regenerate=true" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 모델 호출 없는 기본 양식
curl -s "http://127.0.0.1:8000/records/$RECORD_ID/drafts/landlord/template" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

생성 응답은 `{ "kind", "text", "input_revision", "diagnosis_generation" }`입니다. `GET /records/{record_id}`의 `drafts`에는 저장본과 `is_current`가 함께 옵니다. 진단이 없으면 생성은 `409 diagnosis_required`이고 기본 양식은 `200`입니다. 생성 중 입력이 바뀌면 `409 revision_conflict`(현재 `input_revision` 포함), 진단이 바뀌면 `409 diagnosis_conflict`입니다. 모델 실패는 `502`/`503`/`504`이며 이때 기존 저장본이 유지되므로 앱은 `다시 생성`과 `기본 양식 보기`를 함께 제공합니다. 요청문 편집본을 저장하는 API는 없습니다.

### 업체 검색

```bash
WORK_TYPE_ID=$(curl -s http://127.0.0.1:8000/work-types \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.[0].work_type_id')

curl -s "http://127.0.0.1:8000/providers?region_id=$REGION_ID&work_type_id=$WORK_TYPE_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

응답은 `{ "providers": [...], "is_sample": bool }`이고 각 항목은 `provider_id`, `name`, `phone`(없으면 `null`), `chat_available`, `is_sample`입니다. `chat_available=false`인 업체는 전화 문의만 가능하고 채팅방을 만들 수 없습니다. DB 오류는 빈 결과·샘플이 아니라 `500`입니다. 실제 업체 데이터는 아직 등록되지 않아 현재는 샘플 후보가 반환됩니다.

### 1:1 채팅

```bash
ROOM=$(curl -s -X POST http://127.0.0.1:8000/chat/rooms \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"provider_id\": \"$PROVIDER_ID\", \"record_id\": \"$RECORD_ID\"}")
ROOM_ID=$(echo "$ROOM" | jq -r .room_id)

curl -s "http://127.0.0.1:8000/chat/rooms" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '.[0].unread_count'

curl -s "http://127.0.0.1:8000/chat/rooms/$ROOM_ID/messages?limit=50&offset=0" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -s -X POST "http://127.0.0.1:8000/chat/rooms/$ROOM_ID/read" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl -s -X POST "http://127.0.0.1:8000/chat/rooms/$ROOM_ID/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"client_message_id\": \"$(uuidgen | tr 'A-Z' 'a-z')\", \"content\": \"내일 방문 점검 가능할까요?\"}"
```

실시간 수신은 인증된 WebSocket으로 확인합니다. 토큰을 헤더로 보낼 수 없는 클라이언트는 쿼리를 사용합니다.

```bash
npx wscat -c "ws://127.0.0.1:8000/chat/ws?access_token=$ACCESS_TOKEN"
# 연결 직후: {"type":"ready","user_id":"..."}
# 새 메시지: {"type":"message","room_id":"...","message":{...}}
```

- 요청인은 `POST /chat/rooms`로 방을 만들고 하자 요약을 공유합니다. 같은 요청인·업체 조합은 항상 같은 방을 재사용하고, 같은 기록·같은 요약은 다시 공유되지 않습니다. 새로 저장된 메시지와 새 요약은 참여자 WebSocket으로 전달됩니다.
- 메시지 목록은 `created_at`, `id` 오름차순이며 `{ "messages", "limit", "offset", "has_more" }`입니다. 실시간 이벤트를 놓치거나 재연결하면 `GET /chat/rooms`의 `last_message_at`·`unread_count`를 확인하고, 받은 개수만큼 `offset`을 늘려 이력을 다시 맞춥니다.
- `GET /chat/rooms`의 `unread_count`는 내가 보내지 않은 메시지 중 마지막 읽음 시각 이후 생성된 수입니다. 앱은 방에 들어가 메시지 이력을 받은 직후 `POST /chat/rooms/{room_id}/read`를 호출합니다. 서버가 읽음 시각을 저장하며, 같은 계정의 다른 기기도 같은 상태를 공유합니다. 본인이 보낸 메시지는 미읽음으로 세지 않습니다.
- WebSocket은 누락·만료·서명 오류 토큰을 `4401`로 닫습니다. 연결은 사용자 단위이며 참여 중인 모든 방의 이벤트를 받습니다. 서버는 놓친 이벤트를 재전송하지 않으므로 클라이언트가 백오프로 재연결한 뒤 REST로 동기화합니다. 연결 레지스트리는 단일 API 프로세스 메모리에 있습니다.
- 같은 `client_message_id`와 같은 내용 재전송은 기존 메시지를 반환하고, 다른 내용이면 `409 message_conflict`입니다.
- 참여자(요청인 본인 또는 해당 업체 계정)만 접근할 수 있고, 다른 사용자·다른 업체는 `404`입니다. 업체는 공유 요약만 볼 수 있고 원본 기록에는 접근할 수 없습니다.
- 샘플 업체는 `404`, 계정이 연결되지 않은 업체는 `422`입니다.

## 시연용 다음 질문 흐름 (현재 코드 · MVP 미사용/보류 레거시)

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
- `PATCH /records/{record_id}`는 [API 설계](../design/API_DESIGN.md)대로 `input_revision`을 받지 않습니다. 실제 값이 바뀔 때만 버전을 올리고, 명시한 `null`은 값을 지웁니다.
- 마이그레이션은 로컬 개발을 위해 `auth.users(id)` 스텁을 만들 수 있게 했습니다. Supabase에서는 기존 테이블이 그대로 쓰입니다.
- Supabase의 런타임 DB 연결·RLS·Data API 권한 회수와 ES256 JWKS 조회를 확인했습니다. 실제 사용자 로그인 토큰을 이용한 전체 인증 흐름은 아직 검증하지 않았습니다. 통합 테스트는 로컬 PostgreSQL과 HS256 토큰으로 실행합니다. `005_next_question_grants.sql`은 Home Keeper에 적용했고 적용 이력과 질문 INSERT/UPDATE 권한을 확인했습니다.
- `POST /records/{record_id}/analyze`는 사진과 입력을 multipart로 받아 사진 관찰과 구조화 진단을 저장합니다. YOLO·SAM·비전 LLM 보조 관찰과 텍스트 진단을 분리하고, 원본 사진은 저장하지 않습니다. 입력 스냅샷으로 결과를 만든 뒤 저장 직전에 `input_revision`을 재확인하고, 사진 관찰 상태·진단 결과와 `diagnosis_generation`을 같은 트랜잭션에 저장합니다. `POST /records/{record_id}/diagnosis`는 입력 버전이 같은 진단을 재사용하거나 재생성하며, 실패 시 기존 진단을 보존합니다.
- 회원 프로필 API·화면, 거주 형태, 내 기록 목록과 과거 결과 재열람, 주거 지원 사업 소식지 백엔드(목록·상세·검증 시드·보조금24 수동 동기화), 요청문 생성·기본 양식, 업체 검색, 1:1 채팅 REST·WebSocket·방별 미읽음 수 백엔드는 구현했습니다. 소식지·요청문·업체 검색·채팅 모바일 화면, 사진 원본 비공개 스토리지, 실제 업체·계정 데이터, 회원가입 화면과 4개 탭은 아직 구현하지 않았습니다. 사진 원본 Storage, 소식지 페이지네이션·주기 동기화, 업체 평점·상세, 견적 요청서·제안서·수락은 확정 설계만 있고 코드는 없습니다. 현재 `next-question` 코드의 시연 규칙은 곰팡이 의심 창가 얼룩의 두 질문만 처리하는 레거시/보류 구현이며, 변경된 MVP의 지원 하자 유형은 `균열·벗겨짐·곰팡이`, 시연 지역은 `용인`입니다.
- `records.material`(`006`), `profiles`·용인 지역 시드(`007`), 지역 상하 관계·지원 사업(`008`), 검증 시드(`009`), 업체 계정·채팅·작업 종류 시드(`010`), 채팅 읽음 시각(`011`)은 로컬 테스트 DB에 적용해 검증했습니다(006–009는 로컬 개발 DB에도 적용). Home Keeper의 006–011 적용 여부는 관리자 접근으로 별도 확인해야 합니다.
- 요청문 생성은 `app/llm.py`의 OpenAI 호환 Chat Completions 호출만 사용하고, 외부 모델에는 기록의 하자 입력·진단 결과만 보냅니다. 프로필 개인정보는 보내지 않고 증상 메모의 이메일·휴대전화 번호는 제거합니다. 프롬프트·응답·요청 본문은 로그에 남기지 않습니다. 실제 키 호출은 검증하지 않았고 테스트는 고정 응답을 사용합니다. 증상 메모 원문을 외부 모델 입력으로 계속 사용할지와 동의·고지 방식은 팀 회의 전 미확정이며, 현재 동작은 유지합니다.
- 채팅은 FastAPI REST와 인증된 WebSocket(`/chat/ws`)을 제공합니다. 방별 미읽음 수와 읽음 처리를 구현했고, 읽음 시점은 방 이력 조회 직후입니다. 푸시 알림은 추가하지 않았습니다. `records/messages`(AI 추가 질문)와 `chat_messages`(업체 채팅)는 별도 테이블입니다.
- 보조금24 동기화는 실제 `GOV24_API_KEY`로 `serviceList` 10,891건을 조회하고 주거 제목 필터·지역 확정 후 41건을 로컬 개발 DB에 upsert하는 것까지 확인했습니다. Home Keeper에는 008·009 마이그레이션이 없어 실제 Supabase 동기화는 아직 실행하지 못했습니다. 운영 응답의 주거 키워드·지역명·기한 문구는 첫 적용 후 계속 점검해야 합니다.
- 모바일 앱은 이메일 로그인, 프로필 등록·수정, 내 기록 목록, 사진 1~2장 선택, 위치·재질·증상·외부 분석 동의 입력, 기록 생성 후 샘플 분석 호출, 결과 화면(심각도·추정 원인·해결방안·재발 방지책·샘플 안내·재시도)까지 구현했습니다. 실제 기기/시뮬레이터에서 Supabase 로그인과 API 호출은 아직 검증하지 못했습니다. FormData 요청은 `Content-Type`을 직접 지정하지 않습니다.
