"""Deterministic demo questions used until a real next-question model is wired in."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

SOURCE = "sample"


@dataclass(frozen=True)
class SampleStep:
    key: str
    content: str
    options: tuple[dict[str, str], ...]
    direct_rules: tuple[tuple[str, str], ...]
    replies: tuple[tuple[str, str], ...]


SAMPLE_STEPS = (
    SampleStep(
        key="recurrence",
        content="닦은 뒤 같은 흔적이 다시 생겼나요?",
        options=(
            {"id": "recurred", "label": "다시 생겼어요"},
            {"id": "first_seen", "label": "처음 발견했어요"},
            {"id": "unknown", "label": "잘 모르겠어요"},
        ),
        direct_rules=(
            ("다시 생겼", "recurred"),
            ("또 생겼", "recurred"),
            ("다시 나타났", "recurred"),
            ("또 나타났", "recurred"),
            ("재발", "recurred"),
            ("처음 발견", "first_seen"),
            ("처음 생", "first_seen"),
            ("처음 봤", "first_seen"),
            ("모르", "unknown"),
        ),
        replies=(
            ("recurred", "다시 생긴 흔적이군요. 확인했어요."),
            ("first_seen", "처음 발견하신 흔적이군요. 확인했어요."),
            ("unknown", "아직 모르는 상태로 남겨둘게요."),
        ),
    ),
    SampleStep(
        key="previous_action",
        content="이미 어떤 조치를 했나요?",
        options=(
            {"id": "wiped", "label": "닦아봤어요"},
            {"id": "ventilated", "label": "환기를 했어요"},
            {"id": "none", "label": "아무것도 하지 않았어요"},
            {"id": "unknown", "label": "잘 모르겠어요"},
        ),
        direct_rules=(
            ("닦아봤", "wiped"),
            ("닦았", "wiped"),
            ("환기했", "ventilated"),
            ("환기를 했", "ventilated"),
            ("아무것도", "none"),
            ("아무 조치", "none"),
            ("모르", "unknown"),
        ),
        replies=(
            ("wiped", "닦아보신 점 확인했어요."),
            ("ventilated", "환기하신 점 확인했어요."),
            ("none", "아직 조치하지 않으신 상태로 확인했어요."),
            ("unknown", "조치 여부는 확인되지 않은 상태로 남겨둘게요."),
        ),
    ),
)

_STEP_BY_CONTENT = {step.content: step for step in SAMPLE_STEPS}
_STEP_INDEX = {step.key: index for index, step in enumerate(SAMPLE_STEPS)}


@dataclass(frozen=True)
class SampleDecision:
    reply: str | None
    question: dict[str, Any] | None
    ready_for_diagnosis: bool
    answered_question_ids: tuple[UUID, ...]
    reply_question_id: UUID | None


def match_answer(step: SampleStep, content: str) -> str | None:
    """Match only stored option labels or explicitly documented direct phrases."""
    normalized = content.strip()
    for option in step.options:
        if normalized == option["label"]:
            return option["id"]
    for fragment, option_id in step.direct_rules:
        if fragment in normalized:
            return option_id
    return None


def _reply_for(step: SampleStep, option_id: str) -> str:
    for reply_option_id, reply in step.replies:
        if reply_option_id == option_id:
            return reply
    return "확인했어요."


def _payload_from_step(step: SampleStep) -> dict[str, Any]:
    return {
        "id": None,
        "content": step.content,
        "options": [dict(option) for option in step.options],
    }


def _payload_from_question(question: dict) -> dict[str, Any]:
    return {
        "id": question["id"],
        "content": question["content"],
        "options": list(question["options"] or []),
    }


def _sample_questions(questions: list[dict]) -> list[tuple[dict, SampleStep]]:
    rows = []
    for question in sorted(questions, key=lambda row: row["sequence"]):
        step = _STEP_BY_CONTENT.get(question["content"])
        if step is not None:
            rows.append((question, step))
    return rows


def _latest_linked_user_message(messages: list[dict], question: dict) -> dict | None:
    candidates = [
        message
        for message in messages
        if message["sender"] == "user"
        and message["question_id"] == question["id"]
        and message["sequence"] > question["sequence"]
    ]
    return max(candidates, key=lambda message: message["sequence"], default=None)


def _next_question_payload(
    sample_questions: list[tuple[dict, SampleStep]], start_index: int
) -> dict[str, Any] | None:
    answered_keys = {
        step.key for question, step in sample_questions if question["answered"]
    }
    for step in SAMPLE_STEPS[start_index:]:
        if step.key in answered_keys:
            continue
        existing = next(
            (
                question
                for question, existing_step in sample_questions
                if existing_step.key == step.key
            ),
            None,
        )
        if existing is not None:
            return _payload_from_question(existing)
        return _payload_from_step(step)
    return None


def build_sample_decision(state: dict) -> SampleDecision:
    """Return a deterministic demo turn from the stored conversation snapshot.

    This is the seam to replace with a model call later. It deliberately uses
    only the two sample steps and never infers answers from unrelated messages.
    """
    sample_questions = _sample_questions(state.get("questions", []))
    messages = state.get("messages", [])
    unanswered = [
        (question, step)
        for question, step in sample_questions
        if not question["answered"]
    ]

    if unanswered:
        current_question, step = unanswered[0]
        latest = _latest_linked_user_message(messages, current_question)
        if latest is None:
            return SampleDecision(
                reply=None,
                question=_payload_from_question(current_question),
                ready_for_diagnosis=False,
                answered_question_ids=(),
                reply_question_id=None,
            )

        option_id = match_answer(step, latest["content"])
        if option_id is None:
            return SampleDecision(
                reply="말씀은 확인했어요. 이어서 여쭤볼게요.",
                question=_payload_from_question(current_question),
                ready_for_diagnosis=False,
                answered_question_ids=(),
                reply_question_id=current_question["id"],
            )

        next_question = _next_question_payload(
            sample_questions, _STEP_INDEX[step.key] + 1
        )
        return SampleDecision(
            reply=_reply_for(step, option_id),
            question=next_question,
            ready_for_diagnosis=next_question is None,
            answered_question_ids=(current_question["id"],),
            reply_question_id=current_question["id"],
        )

    next_question = _next_question_payload(sample_questions, 0)
    if next_question is not None:
        return SampleDecision(
            reply=None,
            question=next_question,
            ready_for_diagnosis=False,
            answered_question_ids=(),
            reply_question_id=None,
        )

    # A completed flow may be re-requested after input changes; store the
    # explicit null/null completion so it can be replayed without regenerating.
    return SampleDecision(
        reply=None,
        question=None,
        ready_for_diagnosis=True,
        answered_question_ids=(),
        reply_question_id=None,
    )
