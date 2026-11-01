import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image
from httpx import ASGITransport, AsyncClient

from app.core.code import Code
from app.core.exceptions import BizError
from app.core.cache import refresh_user_roles
from app.system.models import Menu, Role, User
from app.system.models.upload import UploadedImage, UploadSetting
from app.system.schemas.login import JWTPayload
from app.system.security import create_access_token
from app.system.schemas.upload import UploadSettingUpdate
from app.system.services import upload

pytestmark = pytest.mark.asyncio(loop_scope="session")
BASE = "/api/v1/system-manage/uploads"


def png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (12, 8), "red").save(output, format="PNG")
    return output.getvalue()


async def test_upload_roundtrip_and_directory_switch(auth_client, tmp_path: Path):
    first, second = tmp_path / "first", tmp_path / "second"
    configured = await auth_client.patch(f"{BASE}/settings", json={"storageRoot": str(first), "maxSizeMb": 1})
    assert configured.json()["code"] == Code.SUCCESS
    response = await auth_client.post(f"{BASE}/images", files={"file": ("../../photo.png", png(), "text/plain")})
    data = response.json()["data"]
    assert data["name"] == "photo.png"
    assert data["width"] == 12 and data["height"] == 8
    assert "storageRoot" not in data and "relativePath" not in data
    assert data["url"].startswith("/system-manage/uploads/content/")
    record = await UploadedImage.get(key=data["key"])
    assert (first / record.relative_path).read_bytes() == png()
    await auth_client.patch(f"{BASE}/settings", json={"storageRoot": str(second), "maxSizeMb": 2})
    setting = await UploadSetting.get(id=1)
    assert setting.storage_root == str(second)
    assert setting.max_size_mb == 2
    old = await auth_client.get(f"/api/v1{data['url']}")
    assert old.content == png()
    assert old.headers["content-type"] == "image/png"
    assert old.headers["x-content-type-options"] == "nosniff"
    new = await auth_client.post(f"{BASE}/images", files={"file": ("new.png", png(), "image/png")})
    new_record = await UploadedImage.get(key=new.json()["data"]["key"])
    assert Path(new_record.storage_root) == second
    listed = (await auth_client.post(f"{BASE}/search", json={"name": "photo", "size": 1})).json()["data"]
    assert any(item["key"] == data["key"] for item in listed["records"])


async def test_invalid_image_and_size_limit_leave_no_files(auth_client, tmp_path: Path):
    await auth_client.patch(f"{BASE}/settings", json={"storageRoot": str(tmp_path), "maxSizeMb": 1})
    count = await UploadedImage.all().count()
    for content, expected in [(b"<svg><script>alert(1)</script></svg>", Code.UPLOAD_INVALID_IMAGE), (b"", Code.UPLOAD_TOO_LARGE), (b"x" * (1024 * 1024 + 1), Code.UPLOAD_TOO_LARGE)]:
        result = await auth_client.post(f"{BASE}/images", files={"file": ("fake.png", content, "image/png")})
        assert result.json()["code"] == expected
    assert await UploadedImage.all().count() == count
    assert not list(tmp_path.rglob("*.png"))


async def test_anonymous_cannot_upload_or_configure_but_can_view(auth_client, client, tmp_path: Path):
    await auth_client.patch(f"{BASE}/settings", json={"storageRoot": str(tmp_path), "maxSizeMb": 1})
    data = (await auth_client.post(f"{BASE}/images", files={"file": ("public.png", png(), "image/png")})).json()["data"]
    assert (await client.get(f"/api/v1{data['url']}")).content == png()
    assert (await client.get(f"{BASE}/settings")).json()["code"] != Code.SUCCESS
    assert (await client.post(f"{BASE}/search", json={})).json()["code"] != Code.SUCCESS
    assert (await client.post(f"{BASE}/images", files={"file": ("test.png", png(), "image/png")})).json()["code"] != Code.SUCCESS


async def test_path_escape_and_missing_file_rejected(app, tmp_path: Path):
    image = await UploadedImage.create(key="escape-test", name="bad.png", storage_root=str(tmp_path), relative_path="../secret.png", media_type="image/png", size=1, width=1, height=1)
    with pytest.raises(BizError, match=Code.NOT_FOUND):
        await upload.get_image_path(image.key)
    with pytest.raises(BizError, match=Code.NOT_FOUND):
        await upload.get_image_path("not-registered")
    await image.delete()


async def test_failed_setting_does_not_replace_previous(app, tmp_path: Path):
    previous = await upload.update_upload_setting(UploadSettingUpdate(storage_root=str(tmp_path / "good"), max_size_mb=3))
    invalid = tmp_path / "file"
    invalid.write_text("file", encoding="utf-8")
    with pytest.raises(BizError, match=Code.UPLOAD_STORAGE_ERROR):
        await upload.update_upload_setting(UploadSettingUpdate(storage_root=str(invalid), max_size_mb=5))
    persisted = await UploadSetting.get(id=1)
    assert persisted.storage_root == previous.storage_root and persisted.max_size_mb == 3


async def test_database_failure_cleans_saved_file(app, tmp_path: Path, monkeypatch):
    setting = await upload.update_upload_setting(UploadSettingUpdate(storage_root=str(tmp_path), max_size_mb=1))

    async def fail_create(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(UploadedImage, "create", fail_create)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await upload.save_image(png(), "test.png", setting)
    assert not list(tmp_path.rglob("*.png"))


async def test_logged_in_user_without_upload_permission_cannot_write(app, seed_data):
    role = await Role.create(role_name="上传权限测试", role_code="R_UPLOAD_TEST", by_role_home=await Menu.get(route_name="home"))
    user = await User.create(user_name="upload_no_permission", password="unused")
    await user.by_user_roles.add(role)
    await refresh_user_roles(app.state.redis, user.id)
    now = datetime.now(UTC)
    token = create_access_token(data=JWTPayload(data={"userId": user.id, "userName": user.user_name, "tokenType": "accessToken", "tokenVersion": 0}, iat=now, exp=now + timedelta(minutes=5)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver", headers={"Authorization": f"Bearer {token}"}) as client:
            assert (await client.get(f"{BASE}/options")).json()["code"] == Code.SUCCESS
            result = await client.post(f"{BASE}/images", files={"file": ("no.png", png(), "image/png")})
            assert result.json()["code"] == Code.NEED_ANY_BUTTON_PERMISSION
            result = await client.patch(f"{BASE}/settings", json={"storageRoot": "uploads", "maxSizeMb": 1})
            assert result.json()["code"] == Code.PERMISSION_DENIED
    finally:
        await user.delete()
        await role.delete()
