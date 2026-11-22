"""Text diagnosis layer: one structured LLM call over photo observations and
user input, with server-side validation of every field that is shown to users.

Prompts, responses, and request bodies are never logged. Raw coordinates,
masks, and SVG paths are never sent to the text model.
"""

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from psycopg.types.json import Jsonb

from app import llm
from app.auth import get_current_user
from app.config import get_settings
from app.db import read_transaction, transaction
from app.errors import (
    llm_quota_exceeded,
    diagnosis_llm_failed,
    diagnosis_llm_timeout,
    diagnosis_llm_unavailable,
    invalid_request,
    not_found,
    revision_conflict,
)
from app.schemas import (
    ConflictErrorResponse,
    DiagnosisResponse,
    ErrorResponse,
)
from app.vision import OFFICIAL_TYPES, normalize_label

INSPECTION_WORK_TYPE = "원인 점검"
ESTIMATION_NOTICE = (
    "사진 관찰과 입력값을 바탕으로 한 AI 추정 진단입니다. "
    "확정 원인이 아니며 정확한 원인은 현장 점검에서 확인해야 합니다."
)
ACTIONS = ("self_care", "inspection", "provider_consult")

SYSTEM_PROMPT = """\
너는 임차 주택의 하자 사진 관찰과 사용자 입력으로 짧고 구체적인 진단을 만드는 도우미다.
- 주어진 사진 관찰과 사용자 입력만 사용하고, 새로운 사실·업체·금액·일정을 만들지 않는다.
- 확정 원인처럼 단정하지 않고 "가능성", "확인 필요" 같은 표현을 쓴다.
- 심각도 점수는 서버가 계산한다. 너는 checklist 값만 정해진 선택지로 채운다.
- suspected_types에는 "균열", "벗겨짐", "곰팡이"만 넣고, 해당하지 않으면 []로 둔다.
- causes는 최대 2개, care_steps는 최대 3개, prevention_tips는 최대 2개이며 각 항목은 40자 이내로 쓴다.
- 각 원인에는 cause_evidence에 같은 순서로 사진 관찰·입력에서 나온 근거를 한 줄(30자 이내)로 쓴다. 근거가 없는 원인은 쓰지 않는다.
- "환기를 자주 하세요", "전문가와 상담하세요"처럼 근거 없이 어디에나 맞는 일반론은 쓰지 않는다. 위치·흔적에 맞춘 구체적 행동만 쓴다.
- 사진이 흐리거나 흔적이 보이지 않아 판단할 수 없으면 suspected_types를 []로 두고, care_steps 첫 항목에 다시 찍는 방법(거리·밝기·부위)을 쓴다. 지어내지 않는다.
- recommended_action은 "self_care", "inspection", "provider_consult" 중 하나다.
- work_type은 제공된 등록 작업 목록에서만 고르고, 맞는 작업이 없거나 원인이 복합적이면 "원인 점검"을 고른다.
- 출력은 지정된 키만 가진 JSON 객체 하나뿐이다.

"""

# 유형별 참고 카드: 사진에서 의심되는 유형의 카드만 프롬프트에 넣어 입력을 줄입니다(없으면 전부).
_KNOWLEDGE_CARDS = {
    "곰팡이": "- 곰팡이: 결로 → 창틀·외벽 모서리 띠 모양, 물방울 자국 → 결로 부위 건조·단열 점검 / 누수 → 천장·벽 번짐, 갈색 테두리 → 윗집·배관 누수 확인 / 습한 공간 → 화장실·주방 실리콘·줄눈 점 → 실리콘·줄눈 교체",
    "균열": "- 균열: 건조수축 → 가는 머리카락 균열, 도장면 표면 → 보수재 충전 후 경과 관찰 / 구조 변형 → 계단형·사선, 폭이 넓음, 관통 → 점검 필요 / 누수 동반 → 균열 주변 얼룩·백화 → 방수 점검",
    "벗겨짐": "- 벗겨짐: 습기 → 들뜸·부풀음, 물자국 동반 → 원인 습기 먼저 제거 후 재도장·도배 / 노후·접착 불량 → 마른 상태로 벗겨짐 → 해당 면 재시공",
}


def _photo_types(photo_analysis: dict | None) -> list[str]:
    types: list[str] = []
    for photo in (photo_analysis or {}).get("photos") or []:
        for detection in photo.get("detections") or []:
            label = normalize_label(str(detection.get("label") or ""))
            if label in _KNOWLEDGE_CARDS and label not in types:
                types.append(label)
        observation = photo.get("vision_observation")
        if isinstance(observation, dict):
            for label in observation.get("suspected_types") or []:
                if label in _KNOWLEDGE_CARDS and label not in types:
                    types.append(label)
    return types


PROMPT_TEMPLATE = """\
아래 정보로 하자 진단을 만들어 주세요.

[참고 카드: 원인 → 사진 신호 → 대응]
{cards}

[사용자 입력]
- 위치: {location}
- 재질: {material}
- 증상 메모: {symptoms}

[사진 관찰]
{photos}
(화면 점유 비율은 사진에서 차지하는 비율이며 실제 물리 면적이 아님)

[등록된 작업 종류]
{work_types}

[출력 JSON]
{{
  "observations": "사진과 입력에서 확인한 흔적 한 문장",
  "suspected_types": ["균열" | "벗겨짐" | "곰팡이"],
  "checklist": {{
    "moisture_signs": "물기·누수 흔적이 보이거나 입력에 있으면 true, 아니면 false",
    "spread": "없음" | "점" | "띠" | "번짐",
    "crack": "없음" | "가는 균열" | "넓은 균열" | "계단형·관통"
  }},
  "causes": ["추정 원인(최대 2개)"],
  "cause_evidence": ["각 원인의 사진·입력 근거 한 줄"],
  "recommended_action": "self_care" | "inspection" | "provider_consult",
  "care_steps": ["해결 방안(최대 3개)"],
  "prevention_tips": ["재발 방지(최대 2개)"],
  "work_type_id": "등록된 작업 종류의 UUID 또는 null",
  "work_type_name": "등록된 작업 종류 이름 또는 null",
  "work_type_reason": "해당 작업을 추천한 이유 한 줄"
}}
"""

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_REDACTED = "[개인정보 제거]"

router = APIRouter(
    prefix="/records",
    tags=["diagnosis"],
    responses={
        401: {
            "model": ErrorResponse,
            "description": "인증 실패 또는 만료",
        }
    },
)


def _redact(value: str) -> str:
    return _PHONE_PATTERN.sub(_REDACTED, _EMAIL_PATTERN.sub(_REDACTED, value))


def _detection_lines(photo: dict) -> list[str]:
    detections = photo.get("detections") or []
    if not detections:
        return []
    counts: dict[str, int] = {}
    for detection in detections:
        label = str(detection.get("label") or "미분류")
        counts[label] = counts.get(label, 0) + 1
    lines = [
        "- YOLO 탐지 {count}건: {summary}".format(
            count=len(detections),
            summary=", ".join(f"{label} {count}건" for label, count in counts.items()),
        )
    ]
    for detection in detections:
        confidence = detection.get("confidence")
        ratio = detection.get("area_ratio")
        parts = [f"  - {detection.get('label') or '미분류'}"]
        if isinstance(confidence, (int, float)):
            parts.append(f"신뢰도 {confidence * 100:.0f}%")
        if isinstance(ratio, (int, float)):
            parts.append(f"화면 점유 비율 {ratio * 100:.1f}%")
        lines.append(", ".join(parts))
    return lines


def _photo_lines(photo_analysis: dict | None) -> str:
    photos = (photo_analysis or {}).get("photos") or []
    if not photos:
        return "- 사진 분석 결과 없음"
    blocks = []
    for photo in photos:
        role = photo.get("role") or "unknown"
        status = photo.get("status") or "unknown"
        lines = [f"- {role} 사진 (상태: {status})"]
        observation = photo.get("vision_observation")
        if isinstance(observation, dict):
            types = observation.get("suspected_types") or []
            lines.append(
                f"  - 비전 LLM 관찰: 의심 유형 {', '.join(types) if types else '없음'}"
            )
            if observation.get("summary"):
                lines.append(f"  - 관찰 요약: {observation['summary']}")
            if observation.get("approximate_location"):
                lines.append(f"  - 대략 위치: {observation['approximate_location']}")
            if observation.get("unreadable_reason"):
                lines.append(f"  - 판독 불가: {observation['unreadable_reason']}")
        lines += _detection_lines(photo)
        if status == "failed" and not lines[1:]:
            lines.append("  - 분석 실패 또는 판독 불가")
        elif status == "analyzed" and not lines[1:]:
            lines.append("  - 탐지된 흔적 없음")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def build_prompt(record: dict, work_types: list[dict]) -> str:
    symptoms = str(record.get("symptoms") or "").strip()
    types = _photo_types(record.get("photo_observations")) or list(_KNOWLEDGE_CARDS)
    return PROMPT_TEMPLATE.format(
        cards="\n".join(_KNOWLEDGE_CARDS[t] for t in types),
        location=_redact(str(record.get("location") or "미입력")),
        material=_redact(str(record.get("material") or "미입력")),
        symptoms=_redact(symptoms) if symptoms else "미입력",
        photos=_photo_lines(record.get("photo_observations")),
        work_types="\n".join(
            f"- {item['work_type_id']}: {item['name']}" for item in work_types
        )
        or "- 등록된 작업 종류 없음",
    )


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise llm.LlmError(f"Invalid {field}")
    return value.strip()


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise llm.LlmError(f"Invalid {field}")
    items = []
    for item in value:
        if not isinstance(item, str):
            raise llm.LlmError(f"Invalid {field}")
        text = item.strip()
        if text:
            items.append(text)
    return items


def _severity_score(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise llm.LlmError("Invalid severity_score")
    return value


def severity_level(score: int) -> str:
    if score < 40:
        return "low"
    if score < 70:
        return "medium"
    return "high"


def _has_visual_evidence(photo_analysis: dict | None) -> bool:
    for photo in (photo_analysis or {}).get("photos") or []:
        if photo.get("detections"):
            return True
        observation = photo.get("vision_observation")
        if isinstance(observation, dict) and observation.get("suspected_types"):
            return True
    return False


def _work_type_id(
    payload: dict, work_types: list[dict], *, undetermined: bool, complex_cause: bool
) -> tuple[UUID | None, str]:
    inspection = next(
        (item["work_type_id"] for item in work_types if item["name"] == INSPECTION_WORK_TYPE),
        None,
    )
    if undetermined or complex_cause:
        return inspection, "근거가 부족하거나 원인이 복합적이어서 원인 점검을 권장합니다."

    raw_id = payload.get("work_type_id")
    raw_name = payload.get("work_type_name")
    for item in work_types:
        if raw_id is not None and str(item["work_type_id"]) == str(raw_id):
            return item["work_type_id"], _work_type_reason(payload, item["name"])
    if isinstance(raw_name, str):
        for item in work_types:
            if item["name"] == raw_name.strip():
                return item["work_type_id"], _work_type_reason(payload, item["name"])
    return inspection, "등록된 작업 종류와 일치하는 항목이 없어 원인 점검을 권장합니다."


def _work_type_reason(payload: dict, name: str) -> str:
    reason = payload.get("work_type_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return f"{name} 작업이 적합해 보입니다."


# 심각도 기준표 (서버 계산). 숫자는 팀이 조정할 수 있습니다.
_TYPE_POINTS = {"곰팡이": 30, "균열": 25, "벗겨짐": 15}
_SPREAD_POINTS = {"점": 0, "띠": 10, "번짐": 20}
_LOW_CONFIDENCE = 0.5
_LOW_CONFIDENCE_CAP = 60


def _area_points(ratio: float) -> int:
    if ratio < 0.02:
        return 0
    if ratio < 0.10:
        return 10
    if ratio < 0.30:
        return 20
    return 30


def compute_severity(
    suspected_types: list[str],
    checklist: dict,
    photo_analysis: dict | None,
    *,
    location: str,
    material: str,
    symptoms: str,
) -> tuple[int, list[dict]]:
    """Rule-based 0~100 score with a per-factor breakdown shown to users."""
    breakdown: list[dict] = []

    def add(label: str, points: int) -> None:
        if points:
            breakdown.append({"label": label, "points": points})

    main = max(suspected_types, key=lambda t: _TYPE_POINTS.get(t, 0))
    add(main, _TYPE_POINTS.get(main, 0))

    detections = [
        d
        for photo in (photo_analysis or {}).get("photos") or []
        for d in photo.get("detections") or []
    ]
    ratios = [d["area_ratio"] for d in detections if isinstance(d.get("area_ratio"), (int, float))]
    if ratios:
        add("범위", _area_points(max(ratios)))
    else:
        add("범위", _SPREAD_POINTS.get(str(checklist.get("spread") or ""), 0))

    place = f"{location} {material}"
    if any(word in place for word in ("천장", "창틀", "외벽", "베란다")):
        add("위치(누수·결로 경로)", 10)
    elif any(word in place for word in ("화장실", "욕실", "주방")):
        add("위치(습한 공간)", 5)
    if "곰팡이" in suspected_types and re.search(r"안방|침실|(?<!주)방", place):
        add("침실 곰팡이(건강)", 10)

    if checklist.get("moisture_signs") is True or re.search(r"누수|물기|젖|샌|새요|새는|물이", symptoms):
        add("물기·누수", 15)
    if "냄새" in symptoms:
        add("냄새", 5)
    if re.search(r"재발|다시|2주|몇 주|한 달|번지|커지|넓어", symptoms):
        add("재발·진행", 10)
    if checklist.get("crack") in ("넓은 균열", "계단형·관통"):
        add("넓거나 계단형 균열", 20)

    score = min(100, max(0, sum(item["points"] for item in breakdown)))
    confidences = [d["confidence"] for d in detections if isinstance(d.get("confidence"), (int, float))]
    if confidences and max(confidences) < _LOW_CONFIDENCE and score > _LOW_CONFIDENCE_CAP:
        score = _LOW_CONFIDENCE_CAP
        breakdown.append({"label": "탐지 신뢰도 낮음·확인 필요", "points": 0})
    return score, breakdown


def _optional_list(value: Any, field: str, limit: int) -> list[str]:
    if value is None:
        return []
    return _text_list(value, field)[:limit]


def normalize_diagnosis(
    payload: dict,
    *,
    work_types: list[dict],
    photo_analysis: dict | None,
    symptoms: str | None,
    location: str | None = None,
    material: str | None = None,
) -> dict:
    observations = _text(payload.get("observations"), "observations")
    causes = _text_list(payload.get("causes"), "causes")[:2]
    evidence = _optional_list(payload.get("cause_evidence"), "cause_evidence", 2)
    care_steps = _text_list(payload.get("care_steps"), "care_steps")[:3]
    prevention_tips = _text_list(payload.get("prevention_tips"), "prevention_tips")[:2]
    checklist = payload.get("checklist")
    if not isinstance(checklist, dict):
        checklist = {}

    raw_action = payload.get("recommended_action")
    if raw_action not in ACTIONS:
        raise llm.LlmError("Invalid recommended_action")

    raw_types = payload.get("suspected_types")
    if not isinstance(raw_types, list):
        raise llm.LlmError("Invalid suspected_types")
    suspected_types = []
    for item in raw_types:
        if not isinstance(item, str):
            raise llm.LlmError("Invalid suspected_types")
        label = normalize_label(item)
        if label in OFFICIAL_TYPES and label not in suspected_types:
            suspected_types.append(label)

    symptom_text = (symptoms or "").strip()
    undetermined = not suspected_types or (
        not _has_visual_evidence(photo_analysis) and not symptom_text
    )
    breakdown: list[dict] = []
    if undetermined:
        score = None
        level = "undetermined"
        suspected_types = []
        reason = "사진·입력만으로는 하자 흔적을 확인하지 못해 심각도를 계산하지 않았습니다."
        if raw_action == "self_care":
            raw_action = "inspection"
        work_type_id, work_type_reason = _work_type_id(
            payload, work_types, undetermined=True, complex_cause=False
        )
    else:
        score, breakdown = compute_severity(
            suspected_types,
            checklist,
            photo_analysis,
            location=location or "",
            material=material or "",
            symptoms=symptom_text,
        )
        level = severity_level(score)
        reason = " + ".join(f"{item['label']} {item['points']}" for item in breakdown if item["points"])
        reason = f"{reason} = {score}점" if reason else f"{score}점"
        work_type_id, work_type_reason = _work_type_id(
            payload,
            work_types,
            undetermined=False,
            complex_cause=len(suspected_types) > 1,
        )

    return {
        "observations": observations,
        "suspected_types": suspected_types,
        "severity_score": score,
        "severity_level": level,
        "severity_breakdown": breakdown,
        "reason": reason,
        "causes": causes,
        "cause_evidence": evidence[: len(causes)],
        "estimation_notice": ESTIMATION_NOTICE,
        "recommended_action": raw_action,
        "care_steps": care_steps,
        "supplies": [],
        "prevention_tips": prevention_tips,
        "unknowns": [],
        "work_type_id": str(work_type_id) if work_type_id is not None else None,
        "work_type_reason": work_type_reason,
        "source": "llm",
    }


def load_work_types() -> list[dict]:
    with read_transaction() as conn:
        return [
            {"work_type_id": row["id"], "name": row["name"]}
            for row in conn.execute("SELECT id, name FROM work_types ORDER BY name")
        ]


def generate_diagnosis(record: dict, work_types: list[dict]) -> dict:
    payload = llm.generate_json(
        build_prompt(record, work_types), system_prompt=SYSTEM_PROMPT
    )
    return normalize_diagnosis(
        payload,
        work_types=work_types,
        photo_analysis=record.get("photo_observations"),
        symptoms=record.get("symptoms"),
        location=record.get("location"),
        material=record.get("material"),
    )


@router.post(
    "/{record_id}/diagnosis",
    response_model=DiagnosisResponse,
    summary="AI 구조화 진단 생성·재생성",
    description=(
        "저장된 사진 관찰과 현재 위치·재질·증상, DB 작업 종류 목록으로 구조화 진단을 생성합니다.\n\n"
        "- `regenerate=false`이고 저장된 진단이 현재 `input_revision`과 일치하면 모델을 호출하지 않고 그대로 반환합니다.\n"
        "- 재생성하거나 입력이 바뀐 상태에서는 `location`과 `material`이 모두 있어야 하며, 누락 시 `422`입니다.\n"
        "- 진단 생성 중 입력이 바뀌면 아무것도 저장하지 않고 `409`(`revision_conflict`)를 반환합니다.\n"
        "- 사진 흔적과 증상이 모두 없거나 모델이 근거 부족으로 심각도를 비우면 `severity_score=null`, `severity_level=undetermined`, 의심 유형 없음, `원인 점검` 작업으로 저장합니다.\n"
        "- 모델 키 미설정은 기존 진단이 있어도 항상 `503`(`llm_unavailable`)입니다. 호출·응답 형식 오류는 `502`, 제한 시간 초과는 `504`이며 기존 진단은 유지됩니다.\n"
        "- 외부 모델에는 사진별 관찰 요약(라벨·신뢰도·화면 점유 비율)과 마스킹한 위치·재질·증상만 전송합니다. 원시 좌표·마스크·SVG·프로필 개인정보는 전송하지 않습니다."
    ),
    response_description="저장 또는 재사용된 구조화 진단과 입력 버전·생성 번호",
    responses={
        404: {
            "model": ErrorResponse,
            "description": "기록을 찾을 수 없거나 다른 사용자의 기록임",
        },
        409: {"model": ConflictErrorResponse, "description": "진단 생성 중 입력 변경"},
        422: {"model": ErrorResponse, "description": "위치·재질 누락 또는 잘못된 요청"},
        502: {"model": ErrorResponse, "description": "모델 호출 또는 응답 형식 오류"},
        503: {"model": ErrorResponse, "description": "모델 키 미설정"},
        504: {"model": ErrorResponse, "description": "모델 제한 시간 초과"},
    },
)
def create_diagnosis(
    record_id: Annotated[UUID, Path(description="진단할 하자 기록의 UUID.")],
    regenerate: Annotated[
        bool,
        Query(description="`true`면 저장된 진단을 재사용하지 않고 모델로 새로 생성합니다."),
    ] = False,
    owner_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
            (record_id, owner_id),
        ).fetchone()
        if record is None:
            raise not_found()

        if not get_settings().llm_api_key:
            raise diagnosis_llm_unavailable()

        revision = record["input_revision"]
        generation = record["diagnosis_generation"]
        if (
            not regenerate
            and record["diagnosis"] is not None
            and record["diagnosis_revision"] == revision
        ):
            return {
                "record_id": record_id,
                "input_revision": revision,
                "diagnosis_generation": generation,
                "diagnosis": record["diagnosis"],
                "source": record["diagnosis"].get("source", "sample"),
            }

        if not (record["location"] or "").strip() or not (record["material"] or "").strip():
            raise invalid_request("위치와 재질을 입력해야 진단할 수 있습니다.")
        snapshot = dict(record)

    # No row lock is held during the external call; the revision is re-checked below.
    work_types = load_work_types()
    try:
        diagnosis = generate_diagnosis(snapshot, work_types)
    except llm.LlmUnavailable:
        raise diagnosis_llm_unavailable() from None
    except llm.LlmQuotaExceeded:
        raise llm_quota_exceeded() from None
    except llm.LlmTimeout:
        raise diagnosis_llm_timeout() from None
    except llm.LlmError:
        raise diagnosis_llm_failed() from None

    with transaction() as conn:
        record = conn.execute(
            "SELECT * FROM records WHERE id = %s AND owner_id = %s FOR UPDATE",
            (record_id, owner_id),
        ).fetchone()
        if record is None:
            raise not_found()
        if record["input_revision"] != revision:
            raise revision_conflict(record["input_revision"])

        updated = conn.execute(
            """
            UPDATE records
            SET diagnosis = %s,
                diagnosis_revision = %s,
                diagnosis_generation = diagnosis_generation + 1,
                updated_at = now()
            WHERE id = %s
            RETURNING input_revision, diagnosis_generation
            """,
            (Jsonb(diagnosis), revision, record_id),
        ).fetchone()

    return {
        "record_id": record_id,
        "input_revision": updated["input_revision"],
        "diagnosis_generation": updated["diagnosis_generation"],
        "diagnosis": diagnosis,
        "source": diagnosis["source"],
    }
