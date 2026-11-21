"""Supabase Storage access for defect photos.

Only the server key is used; photos live in a private bucket and are exposed to
clients through short-lived signed URLs. When no key is configured, uploads are
skipped and record photo lists stay empty so local/test flows keep working.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID, uuid4

import httpx
from fastapi import UploadFile

from app.config import get_settings
from app.errors import ApiError, invalid_request

MAX_SIDE = 1600
JPEG_QUALITY = 85
REQUEST_TIMEOUT = 20
_MISSING_KEY_MESSAGE = "하자 사진 Storage가 설정되지 않았습니다."


def is_configured() -> bool:
    return bool(get_settings().supabase_storage_key)


def _prepare_jpeg(photo: UploadFile) -> tuple[bytes, int, int]:
    from PIL import Image, ImageOps
    from pillow_heif import register_heif_opener

    register_heif_opener()
    photo.file.seek(0)
    try:
        with Image.open(photo.file) as image:
            resized = ImageOps.exif_transpose(image).convert("RGB")
            resized.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            encoded = BytesIO()
            # Saving new pixels drops EXIF metadata, including GPS data.
            resized.save(encoded, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            return encoded.getvalue(), resized.width, resized.height
    except (OSError, ValueError) as exc:
        raise invalid_request("사진을 읽을 수 없습니다. 올바른 이미지 파일을 사용해 주세요.") from exc


def _headers(settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.supabase_storage_key}"}


def store_photo(
    photo: UploadFile, owner_id: UUID, record_id: UUID, role: str
) -> dict:
    settings = get_settings()
    if not settings.supabase_storage_key:
        raise ApiError(503, "storage_unavailable", _MISSING_KEY_MESSAGE)

    data, width, height = _prepare_jpeg(photo)
    path = f"{owner_id}/{record_id}/{role}_{uuid4().hex}.jpg"
    try:
        response = httpx.post(
            f"{settings.supabase_url}/storage/v1/object/"
            f"{settings.supabase_storage_bucket}/{path}",
            headers={
                **_headers(settings),
                "x-upsert": "false",
                "Content-Type": "image/jpeg",
            },
            content=data,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ApiError(503, "storage_unavailable", _MISSING_KEY_MESSAGE) from exc

    return {"role": role, "storage_path": path, "width": width, "height": height}


def delete_photo(storage_path: str) -> None:
    settings = get_settings()
    if not settings.supabase_storage_key:
        return
    try:
        httpx.delete(
            f"{settings.supabase_url}/storage/v1/object/"
            f"{settings.supabase_storage_bucket}/{storage_path}",
            headers=_headers(settings),
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.HTTPError:
        # Best-effort cleanup after a failed DB write.
        pass


def _signed_url(storage_path: str) -> tuple[str, datetime]:
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.supabase_url}/storage/v1/object/sign/"
            f"{settings.supabase_storage_bucket}/{storage_path}",
            headers=_headers(settings),
            json={"expiresIn": settings.storage_signed_url_ttl_seconds},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(503, "storage_unavailable", _MISSING_KEY_MESSAGE) from exc

    signed = payload.get("signedURL") or payload.get("signedUrl")
    if not isinstance(signed, str) or not signed:
        raise ApiError(503, "storage_unavailable", _MISSING_KEY_MESSAGE)
    url = signed if signed.startswith("http") else f"{settings.supabase_url}/{signed.lstrip('/')}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.storage_signed_url_ttl_seconds
    )
    return url, expires_at


def signed_photos(photo_files: list[dict] | None) -> list[dict]:
    if not photo_files or not is_configured():
        return []
    photos = []
    for item in photo_files:
        if not isinstance(item, dict) or not isinstance(item.get("storage_path"), str):
            continue
        try:
            url, expires_at = _signed_url(item["storage_path"])
        except ApiError:
            continue
        photos.append(
            {
                "role": item.get("role"),
                "url": url,
                "expires_at": expires_at,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    return photos
