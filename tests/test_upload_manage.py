from datetime import datetime
from pathlib import Path

import pytest
from tortoise.queryset import QuerySet

from app.core.code import Code
from app.core.sqids import decode_id, encode_id
from app.system.models.upload import UploadedImage
from app.system.services import upload
from tests.test_upload import BASE, png

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def create_image(client, root: Path, name: str = "manage.png") -> dict:
    await client.patch(f"{BASE}/settings", json={"storageRoot": str(root), "maxSizeMb": 1})
    response = await client.post(f"{BASE}/images", files={"file": (name, png(), "image/png")})
    assert response.json()["code"] == Code.SUCCESS
    return response.json()["data"]


async def test_rename_and_detail_keep_original_url_and_file(auth_client, tmp_path: Path) -> None:
    image = await create_image(auth_client, tmp_path)
    before = await UploadedImage.get(id=decode_id(image["id"]))
    response = await auth_client.patch(f"{BASE}/images/{image['id']}", json={"name": "  商品封面.png  "})
    assert response.json()["code"] == Code.SUCCESS
    renamed = response.json()["data"]
    assert renamed["name"] == "商品封面.png"
    assert renamed["url"] == image["url"]
    detail = (await auth_client.get(f"{BASE}/images/{image['id']}")).json()["data"]
    assert detail["uploader"] == "Soybean"
    assert detail["fmtCreatedAt"] and detail["fmtUpdatedAt"]
    assert "storageRoot" not in detail
    after = await UploadedImage.get(id=before.id)
    assert before.relative_path == after.relative_path
    assert (tmp_path / after.relative_path).read_bytes() == png()
    assert (await auth_client.get(f"/api/v1{image['url']}")).content == png()
    for name in [" ", "../bad.png", "bad\\name.png", "bad\x00.png"]:
        invalid = await auth_client.patch(f"{BASE}/images/{image['id']}", json={"name": name})
        assert invalid.json()["code"] == Code.REQUEST_VALIDATION


async def test_search_by_format_and_upload_time(auth_client, tmp_path: Path) -> None:
    image = await create_image(auth_client, tmp_path, "search-unique.png")
    await UploadedImage.filter(id=decode_id(image["id"])).update(created_at=datetime(2026, 10, 15, 12))
    query = {"name": "search-unique", "mediaType": "image/png", "createdAtStart": "2026-10-15 00:00:00", "createdAtEnd": "2026-10-15 23:59:59"}
    data = (await auth_client.post(f"{BASE}/search", json=query)).json()["data"]
    assert data["total"] == 1 and data["records"][0]["id"] == image["id"]
    assert data["records"][0]["uploader"] == "Soybean"
    assert (await auth_client.post(f"{BASE}/search", json={**query, "mediaType": "image/jpeg"})).json()["data"]["total"] == 0
    assert (await auth_client.post(f"{BASE}/search", json={**query, "createdAtStart": "2026-10-16 00:00:00", "createdAtEnd": None})).json()["data"]["total"] == 0
    assert (await auth_client.post(f"{BASE}/search", json={**query, "createdAtStart": "2026-10-16 00:00:00"})).json()["code"] == Code.REQUEST_VALIDATION


async def test_delete_single_and_batch_remove_records_and_files(auth_client, tmp_path: Path) -> None:
    first = await create_image(auth_client, tmp_path, "delete-first.png")
    record = await UploadedImage.get(id=decode_id(first["id"]))
    path = tmp_path / record.relative_path
    result = await auth_client.delete(f"{BASE}/images/{first['id']}")
    assert result.json()["data"]["deletedCount"] == 1
    assert not path.exists()
    assert not await UploadedImage.filter(id=record.id).exists()
    assert (await auth_client.get(f"/api/v1{first['url']}")).json()["code"] == Code.NOT_FOUND
    second = await create_image(auth_client, tmp_path, "delete-second.png")
    third = await create_image(auth_client, tmp_path, "delete-third.png")
    result = await auth_client.request("DELETE", f"{BASE}/images", json={"ids": [second["id"], third["id"], third["id"]]})
    assert result.json()["data"]["deletedCount"] == 2
    assert not list(tmp_path.rglob("*.png"))
    assert not list(tmp_path.rglob(".deleted-*"))


async def test_partial_missing_batch_does_not_delete_existing(auth_client, tmp_path: Path) -> None:
    image = await create_image(auth_client, tmp_path)
    result = await auth_client.request("DELETE", f"{BASE}/images", json={"ids": [image["id"], encode_id(987654321)]})
    assert result.json()["code"] == Code.NOT_FOUND
    assert await UploadedImage.filter(id=decode_id(image["id"])).exists()
    assert (await auth_client.get(f"/api/v1{image['url']}")).content == png()


async def test_delete_restores_files_when_staging_fails(auth_client, tmp_path: Path, monkeypatch) -> None:
    image = await create_image(auth_client, tmp_path)
    original = upload._stage_deletions

    def fail_staging(images, staged) -> None:
        original(images, staged)
        raise PermissionError("cannot stage another file")

    monkeypatch.setattr(upload, "_stage_deletions", fail_staging)
    result = await auth_client.delete(f"{BASE}/images/{image['id']}")
    assert result.json()["code"] == Code.UPLOAD_STORAGE_ERROR
    assert await UploadedImage.filter(id=decode_id(image["id"])).exists()
    assert (await auth_client.get(f"/api/v1{image['url']}")).content == png()
    assert not list(tmp_path.rglob(".deleted-*"))


async def test_delete_restores_files_when_database_delete_fails(auth_client, tmp_path: Path, monkeypatch) -> None:
    image = await create_image(auth_client, tmp_path)
    original = QuerySet.delete

    def fail_delete(query):
        if query.model is UploadedImage:
            raise RuntimeError("database unavailable")
        return original(query)

    monkeypatch.setattr(QuerySet, "delete", fail_delete)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await upload.delete_images([decode_id(image["id"])])
    assert await UploadedImage.filter(id=decode_id(image["id"])).exists()
    assert (await auth_client.get(f"/api/v1{image['url']}")).content == png()
    assert not list(tmp_path.rglob(".deleted-*"))


async def test_delete_rejects_path_outside_upload_root(app, tmp_path: Path) -> None:
    secret = tmp_path / "keep.png"
    secret.write_bytes(b"keep")
    root = tmp_path / "uploads"
    root.mkdir()
    image = await UploadedImage.create(key="delete-escape", name="bad.png", storage_root=str(root), relative_path="../keep.png", media_type="image/png", size=4, width=1, height=1)
    with pytest.raises(Exception, match=Code.UPLOAD_STORAGE_ERROR):
        await upload.delete_images([image.id])
    assert secret.read_bytes() == b"keep"
    assert await UploadedImage.filter(id=image.id).exists()
    await image.delete()
