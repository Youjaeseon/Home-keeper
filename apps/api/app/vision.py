"""Local YOLO detection followed by consent-gated Meta SAM 3.1 segmentation."""

import asyncio
import base64
import json
import math
import warnings
from dataclasses import asdict
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

import httpx
from fastapi import UploadFile

from app.config import get_settings
from app.errors import ApiError, invalid_request

_model_lock = Lock()


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


def _detect(image, path: str) -> list[dict]:
    try:
        with _model_lock:
            # shortcut: keep the top 16 detections per photo for SAM's object limit; batch when more are needed.
            result = _load_model(path).predict(
                image, verbose=False, save=False, max_det=16,
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
            detections.append({
                "object_id": str(len(detections)),
                "class_id": class_id,
                "label": result.names[class_id],
                "confidence": confidence,
                "bbox": [left, top, right, bottom],
                "image_size": [width, height],
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
        decode_mask_to_rle, decode_mask_to_svg_path, parse_image_stream,
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
        masks[record.object_id] = {
            "encoding": "coco_rle",
            **asdict(decode_mask_to_rle(record.mask)),
            "svg_path": decode_mask_to_svg_path(record.mask),
            "bounds": asdict(bounds),
            "source": "sam-3.1",
        }
    return masks


def analyze_photos(photos: list[UploadFile], roles: list[str], consent: bool) -> dict:
    settings = get_settings()
    results = []
    for photo, role in zip(photos, roles, strict=True):
        try:
            image = _decode_photo(photo)
        except ImportError as exc:
            raise ApiError(503, "vision_unavailable", "사진 분석 의존성이 설치되지 않았습니다.") from exc
        with image:
            detections = _detect(image, settings.yolo_model_path)
            status = "skipped_no_consent" if not consent else "unavailable"
            masks = {}
            if detections and consent and settings.model_api_key:
                try:
                    masks = asyncio.run(_segment(image, detections))
                    status = "no_mask"
                except Exception:
                    # Preserve local detections when the external service fails.
                    status = "failed"
            for detection in detections:
                mask = masks.get(detection["object_id"])
                detection["mask"] = mask
                detection["segmentation_status"] = "completed" if mask else status
            source = "yolo_sam" if masks else "yolo"
            results.append({"role": role, "status": "analyzed", "source": source,
                            "detections": detections})
    source = "yolo_sam" if any(p["source"] == "yolo_sam" for p in results) else "yolo"
    return {
        "applied": True,
        "source": source,
        "notice": (
            "YOLO 사진 탐지 결과입니다. 마스크가 있는 항목은 Meta SAM 3.1 분할 결과입니다. "
            "분할 상태는 항목별로 표시합니다. 심각도·원인·대응 안내는 입력값 기반 샘플 진단입니다."
        ),
        "photos": results,
    }
