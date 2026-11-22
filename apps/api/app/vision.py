"""Photo observation: local YOLO detection, consent-gated Meta SAM 3.1
segmentation, and an independent vision-LLM fallback for photos the detector
could not read."""

import asyncio
import base64
import json
import math
import warnings
from dataclasses import asdict
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Callable

import httpx
from fastapi import UploadFile

from app import llm
from app.config import get_settings
from app.errors import ApiError, invalid_request

_model_lock = Lock()
# SAM segmentation runs here so the diagnosis LLM call does not wait for it.
_sam_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="sam")

# Official defect vocabulary. Unknown model labels are kept verbatim.
LABEL_ALIASES = {
    "crack": "균열",
    "paint_peel": "벗겨짐",
    "peeling": "벗겨짐",
    "mold": "곰팡이",
    "mould": "곰팡이",
    "크랙": "균열",
    "박리": "벗겨짐",
}

OFFICIAL_TYPES = {"균열", "벗겨짐", "곰팡이"}

VISION_SYSTEM_PROMPT = """\
너는 임차 주택 사진에서 하자 흔적을 관찰해 JSON으로만 정리하는 도우미다.
- 사진에서 실제로 보이는 것만 쓴다. 원인·심각도·공사 범위를 추정하지 않는다.
- suspected_types는 "균열", "벗겨짐", "곰팡이" 중 해당하는 것만 넣고 없으면 []로 둔다.
- 좌표·박스·픽셀 값을 만들지 않는다.
- 흐림·어두움·가림 등으로 판독할 수 없으면 unreadable_reason에 이유를 쓰고 summary는 빈 문자열로 둔다.
- 출력은 {"suspected_types": [...], "summary": "...", "approximate_location": "..." | null, "unreadable_reason": "..." | null} JSON 객체 하나뿐이다.
"""

VISION_PROMPT = """\
사진 역할: {role}
사진에서 보이는 하자 흔적을 관찰해 JSON으로 정리해 주세요.
"""


def normalize_label(label: str) -> str:
    text = label.strip()
    return LABEL_ALIASES.get(text.lower(), text)


@lru_cache(maxsize=1)
def _load_model(path: str):
    from ultralytics import YOLO

    # Require a local file so a typo cannot trigger a pretrained-model download.
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    model = YOLO(path)
    if model.task != "detect":
        raise ValueError("A YOLO detection checkpoint is required")
    return model


def _decode_photo(photo: UploadFile):
    from PIL import Image, ImageOps, UnidentifiedImageError
    from pillow_heif import register_heif_opener

    register_heif_opener()
    photo.file.seek(0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(photo.file) as image:
                if image.width * image.height > 25_000_000:
                    raise invalid_request("사진은 2,500만 픽셀 이하여야 합니다.")
                return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise invalid_request("사진을 읽을 수 없습니다. 올바른 이미지 파일을 사용해 주세요.") from exc


def warm_up_detector() -> None:
    """Load the YOLO checkpoint and run one tiny inference so the first analysis is not slow.

    Called once in the background at startup. Missing model or vision extras are ignored.
    """
    path = get_settings().yolo_model_path
    if not path:
        return
    try:
        from PIL import Image

        with Image.new("RGB", (64, 64)) as blank, _model_lock:
            _load_model(path).predict(blank, conf=0.25, max_det=1, verbose=False, save=False)
    except Exception:  # noqa: BLE001 - warm-up is best effort; the request path reports real errors.
        return


def _detect(image, path: str) -> list[dict]:
    try:
        with _model_lock:
            # shortcut: keep the top 16 detections per photo for SAM's object limit; batch when more are needed.
            result = _load_model(path).predict(
                image, conf=0.25, max_det=16, verbose=False, save=False,
            )[0]
        detections = []
        width, height = image.size
        for box in result.boxes:
            coords = box.xyxy[0].tolist()
            if not all(math.isfinite(value) for value in coords):
                raise ValueError("Invalid detection coordinates")
            left = max(0, min(width - 1, math.floor(coords[0])))
            top = max(0, min(height - 1, math.floor(coords[1])))
            right = max(left + 1, min(width, math.ceil(coords[2])))
            bottom = max(top + 1, min(height, math.ceil(coords[3])))
            confidence = float(box.conf.item())
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Invalid confidence")
            class_id = int(box.cls.item())
            raw_label = str(result.names[class_id])
            detections.append({
                "object_id": str(len(detections)),
                "class_id": class_id,
                "label": normalize_label(raw_label),
                "raw_label": raw_label,
                "confidence": confidence,
                "bbox": [left, top, right, bottom],
                "image_size": [width, height],
                "area_ratio": (right - left) * (bottom - top) / (width * height),
                "source": "yolo",
                "segmentation_status": "pending",
                "mask": None,
            })
        return detections
    except Exception as exc:
        raise ApiError(503, "yolo_unavailable", "하자 탐지 모델을 실행할 수 없습니다.") from exc


async def _segment(image, detections: list[dict]) -> dict[str, dict]:
    from meta_sam_parser import (
        FramePrompt, PromptBox, PromptObject, build_object_prompt,
        decode_mask_to_raster, decode_mask_to_rle, decode_mask_to_svg_path,
        parse_image_stream,
    )

    settings = get_settings()
    prompt = build_object_prompt(
        size=image.size,
        objects=[
            PromptObject(id=d["object_id"], prompts=[FramePrompt(box=PromptBox(*d["bbox"]))])
            for d in detections
        ],
    )
    encoded = BytesIO()
    image.save(encoded, format="PNG")
    image_url = "data:image/png;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")

    async def events(response):
        data = []
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif not line and data:
                payload = "\n".join(data)
                data.clear()
                if payload == "[DONE]":
                    return
                yield json.loads(payload)
        if data and "\n".join(data) != "[DONE]":
            yield json.loads("\n".join(data))

    async with asyncio.timeout(settings.sam_timeout_seconds):
        async with httpx.AsyncClient(timeout=settings.sam_timeout_seconds) as client:
            async with client.stream(
                "POST", "https://api.meta.ai/v1/responses",
                headers={"Authorization": f"Bearer {settings.model_api_key}"},
                json={"model": "sam-3.1", "stream": True, "input": [
                    {"type": "message", "role": "user", "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_url},
                    ]},
                ]},
            ) as response:
                response.raise_for_status()
                async with parse_image_stream(events(response)) as stream:
                    result = await stream.final_result()
    if (result.outcome.status != "completed" or result.diagnostics
            or any(record.kind == "text" for record in result.records)):
        raise ValueError("Incomplete or malformed segmentation")
    masks = {}
    expected_ids = {d["object_id"] for d in detections}
    width, height = image.size
    for record in result.records:
        if record.kind != "mask":
            continue
        bounds = record.bounds
        if (record.object_id not in expected_ids or record.object_id in masks
                or not 0 <= bounds.left < bounds.right <= width
                or not 0 <= bounds.top < bounds.bottom <= height):
            raise ValueError("Invalid segmentation object or bounds")
        raster = decode_mask_to_raster(record.mask)
        coverage = sum(raster) / len(raster) if raster else 0.0
        bounds_ratio = (
            (bounds.right - bounds.left) * (bounds.bottom - bounds.top)
            / (width * height)
        )
        masks[record.object_id] = {
            "encoding": "coco_rle",
            **asdict(decode_mask_to_rle(record.mask)),
            "svg_path": decode_mask_to_svg_path(record.mask),
            "bounds": asdict(bounds),
            "source": "sam-3.1",
            # Internal until analysis copies it onto the detection.
            "_area_ratio": coverage * bounds_ratio,
        }
    return masks


def _vision_image(image) -> str:
    from PIL import Image

    resized = image.copy()
    resized.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
    encoded = BytesIO()
    resized.save(encoded, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")


def _vision_observation(payload: dict) -> dict:
    types = payload.get("suspected_types")
    if not isinstance(types, list):
        raise ValueError("Invalid suspected_types")
    suspected = []
    for item in types:
        if not isinstance(item, str):
            raise ValueError("Invalid suspected_types item")
        label = normalize_label(item)
        if label in OFFICIAL_TYPES and label not in suspected:
            suspected.append(label)

    reason = payload.get("unreadable_reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("Invalid unreadable_reason")
    reason = (reason or "").strip() or None

    summary = payload.get("summary")
    if not isinstance(summary, str):
        raise ValueError("Invalid summary")
    summary = summary.strip()
    if not summary and reason is None:
        raise ValueError("Empty observation")

    location = payload.get("approximate_location")
    if location is not None and not isinstance(location, str):
        raise ValueError("Invalid approximate_location")

    return {
        "suspected_types": suspected,
        "summary": summary,
        "approximate_location": (location or "").strip() or None,
        "unreadable_reason": reason,
    }


def _observe(image, role: str) -> dict | None:
    """Independent vision-LLM observation; None means the call or output failed."""
    settings = get_settings()
    try:
        payload = llm.generate_json(
            VISION_PROMPT.format(role=role),
            system_prompt=VISION_SYSTEM_PROMPT,
            image_data_url=_vision_image(image),
            model=settings.vision_llm_model or settings.llm_model,
        )
        return _vision_observation(payload)
    except (llm.LlmError, ValueError):
        return None


def _aggregate_source(photos: list[dict]) -> str:
    sources = {photo["source"] for photo in photos}
    if sources & {"yolo", "yolo_sam"} and "vision_llm" in sources:
        return "yolo_vision_llm"
    if "vision_llm" in sources:
        return "vision_llm"
    if "yolo_sam" in sources:
        return "yolo_sam"
    if "yolo" in sources:
        return "yolo"
    return "sample"


def analyze_photos(photos: list[UploadFile], roles: list[str], consent: bool) -> dict:
    result, finish = start_photo_analysis(photos, roles, consent)
    return finish()


def _apply_masks(detections: list[dict], masks: dict, status: str) -> None:
    for detection in detections:
        mask = masks.get(detection["object_id"])
        if mask is not None:
            ratio = mask.pop("_area_ratio", None)
            if ratio is not None:
                detection["area_ratio"] = ratio
        detection["mask"] = mask
        detection["segmentation_status"] = "completed" if mask else status


def start_photo_analysis(
    photos: list[UploadFile], roles: list[str], consent: bool
) -> tuple[dict, Callable[[], dict]]:
    """YOLO/vision now; SAM segmentation in the background.

    Returns the photo analysis (YOLO box ratios for now) and finish(), which
    waits for SAM, applies masks and precise area ratios, and returns the same dict.
    """
    settings = get_settings()
    pending: list[tuple[dict, list[dict], object]] = []
    if settings.yolo_model_path and not settings.llm_api_key:
        raise ApiError(
            503,
            "llm_unavailable",
            "진단 모델이 설정되지 않았습니다. LLM_API_KEY를 설정해 주세요.",
        )

    results = []
    for photo, role in zip(photos, roles, strict=True):
        try:
            image = _decode_photo(photo)
        except ImportError as exc:
            raise ApiError(503, "vision_unavailable", "사진 분석 의존성이 설치되지 않았습니다.") from exc
        with image:
            vision_allowed = consent and bool(settings.llm_api_key)
            detections = []
            yolo_failed = False
            if settings.yolo_model_path:
                try:
                    detections = _detect(image, settings.yolo_model_path)
                except ApiError:
                    yolo_failed = True

            if detections:
                entry = {
                    "role": role,
                    "status": "analyzed",
                    "source": "yolo",
                    "detections": detections,
                    "vision_observation": None,
                }
                results.append(entry)
                if consent and settings.model_api_key:
                    future = _sam_pool.submit(
                        lambda img, dets: asyncio.run(_segment(img, dets)),
                        image.copy(),
                        detections,
                    )
                    pending.append((entry, detections, future))
                else:
                    status = "skipped_no_consent" if not consent else "unavailable"
                    _apply_masks(detections, {}, status)
            elif vision_allowed:
                observation = _observe(image, role)
                unreadable = observation is None or observation["unreadable_reason"] is not None
                results.append({
                    "role": role,
                    "status": "failed" if unreadable else "analyzed",
                    "source": "vision_llm",
                    "detections": [],
                    "vision_observation": observation,
                })
            elif yolo_failed:
                results.append({
                    "role": role,
                    "status": "failed",
                    "source": "yolo",
                    "detections": [],
                    "vision_observation": None,
                })
            elif settings.yolo_model_path:
                # The detector ran and found nothing; no external photo call was allowed.
                results.append({
                    "role": role,
                    "status": "analyzed",
                    "source": "yolo",
                    "detections": [],
                    "vision_observation": None,
                })
            else:
                results.append({
                    "role": role,
                    "status": "not_analyzed",
                    "source": "sample",
                    "detections": [],
                    "vision_observation": None,
                })

    source = _aggregate_source(results)
    analysis = {
        "applied": source != "sample",
        "source": source,
        "notice": (
            "YOLO 사진 탐지와 Meta SAM 3.1 분할, 비전 LLM 보조 관찰 결과입니다. "
            "비전 LLM은 YOLO가 읽지 못한 사진만 독립적으로 관찰했습니다. "
            "심각도·원인·대응 안내는 사진 관찰과 입력값을 바탕으로 한 AI 추정입니다."
        ),
        "photos": results,
    }

    def finish() -> dict:
        for entry, detections, future in pending:
            masks: dict = {}
            status = "no_mask"
            try:
                masks = future.result(timeout=settings.sam_timeout_seconds + 5)
            except Exception:
                # Preserve local detections when the external service fails.
                status = "failed"
            _apply_masks(detections, masks, status)
            if masks:
                entry["source"] = "yolo_sam"
        pending.clear()
        analysis["source"] = _aggregate_source(results)
        analysis["applied"] = analysis["source"] != "sample"
        return analysis

    return analysis, finish
