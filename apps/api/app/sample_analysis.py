"""Deterministic sample analysis used until real image and diagnosis models are wired in."""

from dataclasses import dataclass
from typing import Any

SOURCE = "sample"
MAX_PHOTO_BYTES = 10 * 1024 * 1024
PHOTO_ROLES = ("overview", "closeup")


@dataclass(frozen=True)
class SampleAnalysis:
    photo_analysis: dict[str, Any]
    diagnosis: dict[str, Any]


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _defect_types(text: str) -> list[str]:
    defects: list[str] = []
    if any(term in text for term in ("곰팡이", "검은", "얼룩")):
        defects.append("곰팡이")
    if any(term in text for term in ("크랙", "균열", "갈라")):
        defects.append("균열")
    if any(term in text for term in ("벗겨", "들뜨", "박리", "도배")):
        defects.append("벗겨짐")
    return defects or ["표면 이상"]


def _severity_terms(text: str) -> bool:
    return any(term in text for term in ("재발", "다시", "번지", "넓", "심해"))


def _leak_terms(text: str) -> bool:
    return any(term in text for term in ("누수", "물이 새", "결로", "젖"))


def build_sample_analysis(
    *,
    location: str,
    material: str,
    symptoms: str | None,
    photo_roles: list[str],
    external_analysis_consent: bool,
) -> SampleAnalysis:
    """Build a deterministic demo result from submitted fields, never photo bytes.

    This is the seam to replace with image detection and diagnosis model calls.
    """
    location = location.strip()
    material = material.strip()
    symptom_text = (symptoms or "").strip()
    text = " ".join(part for part in (location, material, symptom_text) if part)
    defects = _defect_types(text)

    score = 35
    if "곰팡이" in defects:
        score += 25
    if "균열" in defects:
        score += 15
    if "벗겨짐" in defects:
        score += 15
    if _severity_terms(text):
        score += 15
    if _leak_terms(text):
        score += 10
    if material in {"실리콘", "창틀"} and "곰팡이" in defects:
        score += 5
    if material in {"벽지", "도배"} and "벗겨짐" in defects:
        score += 5
    score = max(20, min(90, score))
    level = "low" if score < 40 else "medium" if score < 70 else "high"
    recommended_action = (
        "inspection"
        if score >= 70 or "곰팡이" in defects or _severity_terms(text) or _leak_terms(text)
        else "self_care"
    )

    cause_map = {
        "곰팡이": ["창가 결로로 인한 표면 습기 축적 가능성", "실리콘·창틀 틈새의 습기 잔류 가능성"],
        "균열": ["도장·마감재 노화로 인한 균열 가능성", "구조물의 미세한 움직임 가능성"],
        "벗겨짐": ["습기나 접착력 저하로 인한 마감재 박리 가능성", "도장면 노화 가능성"],
        "표면 이상": ["입력한 위치·재질만으로는 원인을 단정하기 어렵습니다."],
    }
    causes = _unique([cause for defect in defects for cause in cause_map.get(defect, [])])

    if recommended_action == "inspection":
        care_steps = [
            "표면을 무리하게 긁거나 뜯지 말고 현재 상태를 유지하세요.",
            "누수·결로가 의심되면 임대인이나 관리실에 점검을 요청하세요.",
        ]
    else:
        care_steps = [
            "마른 천으로 표면 먼지를 닦고 충분히 환기하세요.",
            "증상이 번지거나 다시 나타나면 점검을 요청하세요.",
        ]
    supplies = ["마스크", "고무장갑", "마른 천"]
    if "곰팡이" in defects:
        supplies.append("곰팡이 제거제")
    if "균열" in defects or "벗겨짐" in defects:
        supplies.append("보수용 테이프")

    prevention_tips = [
        "아침·저녁 짧게라도 맞통풍 환기를 유지하세요.",
        "결로가 맺히면 바로 물기를 닦아 습기를 남기지 마세요.",
        "같은 증상이 반복되면 원인 점검을 받으세요.",
    ]
    unknowns = [
        "사진에서 확인할 흔적의 범위와 정도(사진 분석 미수행)",
        "누수·결로 등 실제 원인",
        "이전 조치와 재발 여부",
    ]
    if "곰팡이" in defects:
        work_type_reason = "곰팡이 제거와 습기 원인 점검을 함께 진행하는 것이 적합합니다."
    elif "균열" in defects:
        work_type_reason = "균열 보수와 구조적 원인 점검이 필요할 수 있습니다."
    elif "벗겨짐" in defects:
        work_type_reason = "마감재 보수와 습기 원인 점검이 필요할 수 있습니다."
    else:
        work_type_reason = "입력한 증상만으로는 작업 범위를 확정하기 어려워 원인 점검이 필요합니다."

    notice = (
        "샘플 결과입니다. 실제 사진 분석과 외부 AI 호출은 수행하지 않았습니다. "
        "입력한 위치·재질·증상만 사용했습니다."
        + (" 외부 분석 동의가 있었지만 샘플 모드에서는 전송하지 않았습니다."
           if external_analysis_consent
           else " 외부 분석 동의가 없어 외부 전송도 하지 않았습니다.")
    )
    photo_analysis = {
        "applied": False,
        "notice": notice,
        "photos": [
            {
                "role": role,
                "status": "not_analyzed",
                "source": SOURCE,
                "detections": [],
                "vision_observation": None,
            }
            for role in photo_roles
        ],
        "source": SOURCE,
    }

    symptoms_label = symptom_text or "증상 메모 없음"
    diagnosis = {
        "observations": (
            f"사진 분석은 수행되지 않았습니다. 입력한 위치({location}), 재질({material}), "
            f"{symptoms_label}을 기준으로 만든 샘플 관찰 요약입니다."
        ),
        "suspected_types": defects,
        "severity_score": score,
        "severity_level": level,
        "reason": (
            f"입력값 기준 샘플 심각도 {score}%({level})입니다. "
            f"{', '.join(defects)} 관련 입력이 있었지만, 실제 사진 분석 없이 만든 참고용 수치입니다."
        ),
        "causes": causes,
        "estimation_notice": (
            "이 결과는 사진을 실제로 분석하지 않고 입력한 위치·재질·증상만으로 만든 샘플입니다. "
            "실제 AI 진단이나 현장 점검 결과가 아니며, 정확한 원인은 현장 확인이 필요합니다."
        ),
        "recommended_action": recommended_action,
        "care_steps": care_steps,
        "supplies": supplies,
        "prevention_tips": prevention_tips,
        "unknowns": unknowns,
        "work_type_id": None,
        "work_type_reason": work_type_reason,
        "source": SOURCE,
    }
    return SampleAnalysis(photo_analysis=photo_analysis, diagnosis=diagnosis)
