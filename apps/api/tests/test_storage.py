import asyncio
import threading
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import UploadFile
from PIL import Image
from psycopg.types.json import Jsonb

from app import storage
from app.main import app
from conftest import PNG_1X1, auth_headers


def _settings(**overrides):
    base = SimpleNamespace(
        supabase_url="https://project.supabase.co",
        supabase_storage_bucket="defect-photos",
        supabase_storage_key="server-key",
        storage_signed_url_ttl_seconds=300,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _jpeg(width=2000, height=1000, orientation=None):
    image = Image.new("RGB", (width, height), "white")
    data = BytesIO()
    if orientation is None:
        image.save(data, format="JPEG")
    else:
        exif = Image.Exif()
        exif[274] = orientation
        image.save(data, format="JPEG", exif=exif)
    return data.getvalue()


class _Response:
    def __init__(self, payload=None):
        self._payload = payload or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_store_photo_resizes_rotates_and_strips_exif(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(storage, "get_settings", lambda: _settings())
    monkeypatch.setattr(storage.httpx, "post", fake_post)
    owner_id, record_id = uuid4(), uuid4()
    upload = UploadFile(BytesIO(_jpeg(orientation=6)), filename="photo.jpg")

    item = storage.store_photo(upload, owner_id, record_id, "overview")

    assert item["role"] == "overview"
    assert item["width"] == 800
    assert item["height"] == 1600
    assert item["storage_path"].startswith(
        f"{owner_id}/{record_id}/overview_"
    )
    assert item["storage_path"].endswith(".jpg")
    assert captured["url"] == (
        f"https://project.supabase.co/storage/v1/object/"
        f"defect-photos/{item['storage_path']}"
    )
    assert captured["headers"]["x-upsert"] == "false"
    assert captured["headers"]["Content-Type"] == "image/jpeg"
    assert captured["headers"]["Authorization"] == "Bearer server-key"

    stored = Image.open(BytesIO(captured["content"]))
    assert stored.size == (800, 1600)
    assert len(stored.getexif()) == 0
    upload.file.close()


def test_signed_photos_returns_short_lived_absolute_url(monkeypatch):
    monkeypatch.setattr(storage, "get_settings", lambda: _settings())
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _Response({"signedURL": "/object/sign/defect-photos/a/b.jpg?token=t"})

    monkeypatch.setattr(storage.httpx, "post", fake_post)
    photos = storage.signed_photos(
        [{"role": "closeup", "storage_path": "a/b.jpg", "width": 10, "height": 20}]
    )

    assert captured["url"] == (
        "https://project.supabase.co/storage/v1/object/sign/defect-photos/a/b.jpg"
    )
    assert captured["json"] == {"expiresIn": 300}
    assert photos[0]["role"] == "closeup"
    assert photos[0]["width"] == 10
    assert photos[0]["height"] == 20
    # Supabase returns a path relative to the Storage API; the URL must keep /storage/v1.
    assert photos[0]["url"].startswith(
        "https://project.supabase.co/storage/v1/object/sign/defect-photos/a/b.jpg?token="
    )
    assert photos[0]["expires_at"].tzinfo is not None


def test_storage_without_key_skips_upload_and_signing(monkeypatch):
    monkeypatch.setattr(
        storage, "get_settings", lambda: _settings(supabase_storage_key=None)
    )
    assert storage.is_configured() is False
    assert storage.signed_photos([{"role": "overview", "storage_path": "x"}]) == []
    with pytest.raises(Exception):
        storage.store_photo(
            UploadFile(BytesIO(_jpeg()), filename="photo.jpg"), uuid4(), uuid4(), "overview"
        )


def test_analyze_without_storage_key_keeps_photo_files_empty(
    client, user_factory, token_for, record_factory, admin
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    response = client.post(
        f"/records/{record_id}/analyze",
        headers=auth_headers(token),
        data={
            "photo_roles": "overview",
            "external_analysis_consent": "false",
            "location": "안방",
            "material": "벽지",
        },
        files=[("photos", ("photo.png", PNG_1X1, "image/png"))],
    )
    assert response.status_code == 200, response.text
    row = admin.execute(
        "SELECT photo_files FROM records WHERE id = %s", (record_id,)
    ).fetchone()
    assert row["photo_files"] == []
    detail = client.get(f"/records/{record_id}", headers=auth_headers(token)).json()
    assert detail["photos"] == []


def test_failed_analyze_deletes_uploaded_objects(
    client, user_factory, token_for, record_factory, monkeypatch
):
    from app.sample_analysis import build_sample_analysis as real_analysis

    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    deleted = []
    started = threading.Event()
    release = threading.Event()

    monkeypatch.setattr(storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        storage,
        "store_photo",
        lambda photo, owner, record, role: {
            "role": role,
            "storage_path": f"{role}/stored.jpg",
            "width": 10,
            "height": 10,
        },
    )
    monkeypatch.setattr(storage, "delete_photo", deleted.append)

    def slow(**kwargs):
        started.set()
        if not release.wait(10):
            raise AssertionError("test did not release the analysis")
        return real_analysis(**kwargs)

    monkeypatch.setattr("app.records.build_sample_analysis", slow)
    form = {
        "photo_roles": ["overview"],
        "external_analysis_consent": "false",
        "location": "안방",
        "material": "벽지",
    }

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            pending = asyncio.create_task(
                async_client.post(
                    f"/records/{record_id}/analyze",
                    headers=auth_headers(token),
                    data=form,
                    files=[("photos", ("photo.png", PNG_1X1, "image/png"))],
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 10)
                patched = await async_client.patch(
                    f"/records/{record_id}",
                    headers=auth_headers(token),
                    json={"location": "바뀐 위치"},
                )
                assert patched.status_code == 200
            finally:
                release.set()
            return await pending

    response = asyncio.run(scenario())
    assert response.status_code == 409
    assert deleted == ["overview/stored.jpg"]


def test_record_photos_are_owner_only(
    client, user_factory, token_for, record_factory, admin, monkeypatch
):
    user_id = user_factory()
    other_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    admin.execute(
        "UPDATE records SET photo_files = %s WHERE id = %s",
        (Jsonb([{"role": "overview", "storage_path": "a/b.jpg", "width": 10, "height": 20}]), record_id),
    )
    monkeypatch.setattr(storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        storage,
        "signed_photos",
        lambda _files: [
            {
                "role": "overview",
                "url": "https://project.supabase.co/signed",
                "expires_at": "2026-01-01T00:00:00Z",
                "width": 10,
                "height": 20,
            }
        ],
    )

    owner = client.get(f"/records/{record_id}", headers=auth_headers(token))
    assert owner.status_code == 200
    assert owner.json()["photos"][0]["url"].endswith("/signed")

    denied = client.get(
        f"/records/{record_id}", headers=auth_headers(token_for(other_id))
    )
    assert denied.status_code == 404
