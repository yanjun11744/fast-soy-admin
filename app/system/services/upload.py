"""本地图片存储：只公开已登记图片，不挂载任意目录。"""

import asyncio
import io
import warnings
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from tortoise.transactions import in_transaction

from app.core.code import Code
from app.core.config import APP_SETTINGS
from app.core.crud import get_db_conn
from app.core.ctx import CTX_USER, CTX_USER_ID
from app.core.exceptions import BizError
from app.system.models.admin import User
from app.system.models.upload import UploadedImage, UploadSetting
from app.system.radar.developer import radar_log
from app.system.schemas.upload import ImageSearch, ImageUpdate, UploadSettingUpdate

IMAGE_FORMATS = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"), "GIF": (".gif", "image/gif"), "WEBP": (".webp", "image/webp")}
IMAGE_URL_PREFIX = "/system-manage/uploads/content/"


async def get_upload_setting() -> UploadSetting:
    setting, _ = await UploadSetting.get_or_create(id=1, defaults={"storage_root": "uploads", "max_size_mb": 5})
    return setting


def resolve_root(value: str) -> Path:
    path = Path(value.strip()).expanduser()
    return (path if path.is_absolute() else APP_SETTINGS.BASE_DIR / path).resolve()


def _prepare_directory(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    probe = root / f".upload-check-{uuid4().hex}"
    try:
        with probe.open("xb") as output:
            output.write(b"")
    finally:
        probe.unlink(missing_ok=True)


async def update_upload_setting(obj: UploadSettingUpdate) -> UploadSetting:
    try:
        if not obj.storage_root.strip():
            raise ValueError("empty path")
        root = resolve_root(obj.storage_root)
        await run_in_threadpool(_prepare_directory, root)
    except (OSError, ValueError) as exc:
        raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="上传目录不可用，请检查路径及写入权限") from exc
    setting = await get_upload_setting()
    setting.storage_root = str(root)
    setting.max_size_mb = obj.max_size_mb
    await setting.save()
    radar_log("更新图片存储配置", data={"maxSizeMb": obj.max_size_mb})
    return setting


def _inspect_image(content: bytes) -> tuple[str, str, int, int]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                fmt = image.format or ""
                if fmt not in IMAGE_FORMATS:
                    raise ValueError("unsupported image")
                width, height = image.size
                if width * height > 25_000_000:
                    raise ValueError("too many pixels")
                image.verify()
            # JPEG.verify() does not decode pixels; load once to reject truncated payloads.
            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
        extension, media_type = IMAGE_FORMATS[fmt]
        return extension, media_type, width, height
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise BizError(code=Code.UPLOAD_INVALID_IMAGE, msg="图片内容无效；仅支持 JPG、PNG、GIF、WebP，且不超过 2500 万像素") from exc


def _write_image(root: Path, relative: str, content: bytes) -> None:
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="图片存储路径无效")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        try:
            output.write(content)
        except BaseException:
            target.unlink(missing_ok=True)
            raise


async def save_image(content: bytes, name: str, setting: UploadSetting) -> dict:
    if not content or len(content) > setting.max_size_mb * 1024 * 1024:
        raise BizError(code=Code.UPLOAD_TOO_LARGE, msg=f"图片不能为空且不能超过 {setting.max_size_mb} MB")
    extension, media_type, width, height = await run_in_threadpool(_inspect_image, content)
    key = uuid4().hex
    root = resolve_root(setting.storage_root)
    relative = f"{datetime.now():%Y/%m/%d}/{key}{extension}"
    try:
        await run_in_threadpool(_write_image, root, relative, content)
    except OSError as exc:
        raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="图片保存失败，请检查存储目录及剩余空间") from exc
    try:
        image = await UploadedImage.create(
            key=key,
            name=Path(name.replace("\\", "/")).name[:255] or f"image{extension}",
            storage_root=str(root),
            relative_path=relative,
            media_type=media_type,
            size=len(content),
            width=width,
            height=height,
            created_by=str(CTX_USER_ID.get() or ""),
        )
    except BaseException:
        await asyncio.shield(run_in_threadpool((root / relative).unlink, missing_ok=True))
        raise
    radar_log("上传图片", data={"key": key, "size": len(content)})
    return await image_data(image)


async def image_data(image: UploadedImage) -> dict:
    data = await image.to_dict(exclude_fields=["storage_root", "relative_path"])
    data["url"] = f"{IMAGE_URL_PREFIX}{image.key}"
    data["uploader"] = image.created_by or ""
    return data


async def search_images(query: ImageSearch) -> tuple[int, list[dict]]:
    images = UploadedImage.all()
    if query.name:
        images = images.filter(name__icontains=query.name.strip())
    if query.media_type:
        images = images.filter(media_type=query.media_type)
    if query.created_at_start:
        images = images.filter(created_at__gte=query.created_at_start)
    if query.created_at_end:
        images = images.filter(created_at__lte=query.created_at_end)
    total = await images.count()
    records = await images.order_by("-id").offset((query.current - 1) * query.size).limit(query.size)
    data = [await image_data(image) for image in records]
    # Earlier versions stored numeric user IDs. Resolve them in one query, without N+1 lookups.
    user_ids = {int(image.created_by) for image in records if image.created_by and image.created_by.isdecimal()}
    users = await User.filter(id__in=user_ids).values("id", "user_name") if user_ids else []
    names = {str(user["id"]): user["user_name"] for user in users}
    for item in data:
        item["uploader"] = names.get(item["createdBy"], item["uploader"])
    return total, data


async def get_image(item_id: int) -> dict:
    image = await UploadedImage.get_or_none(id=item_id)
    if not image:
        raise BizError(code=Code.NOT_FOUND, msg="图片不存在")
    data = await image_data(image)
    if image.created_by and image.created_by.isdecimal():
        user = await User.get_or_none(id=int(image.created_by))
        if user:
            data["uploader"] = user.user_name
    return data


async def update_image(item_id: int, obj: ImageUpdate) -> dict:
    async with in_transaction(get_db_conn(UploadedImage)):
        image = await UploadedImage.filter(id=item_id).select_for_update().first()
        if not image:
            raise BizError(code=Code.NOT_FOUND, msg="图片不存在")
        image.name = obj.name
        user = CTX_USER.get()
        image.updated_by = user.user_name if user else None
        await image.save(update_fields=["name", "updated_by", "updated_at"])
    radar_log("重命名上传图片", data={"key": image.key})
    return await get_image(item_id)


def _image_target(image: UploadedImage) -> Path:
    root = Path(image.storage_root).resolve()
    target = (root / image.relative_path).resolve()
    if not target.is_relative_to(root):
        raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="图片存储路径无效")
    return target


def _stage_deletions(images: list[UploadedImage], staged: list[tuple[Path, Path]]) -> None:
    for image in images:
        target = _image_target(image)
        if not target.exists():
            continue  # Missing files must not prevent cleaning up stale records.
        if not target.is_file():
            raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="图片存储路径不是文件")
        backup = target.with_name(f".deleted-{uuid4().hex}")
        target.rename(backup)
        staged.append((target, backup))


def _restore_deletions(staged: list[tuple[Path, Path]]) -> None:
    for target, backup in reversed(staged):
        backup.rename(target)


async def delete_images(ids: list[int]) -> int:
    ids = sorted(set(ids))
    staged: list[tuple[Path, Path]] = []
    try:
        async with in_transaction(get_db_conn(UploadedImage)):
            images = await UploadedImage.filter(id__in=ids).order_by("id").select_for_update()
            if len(images) != len(ids):
                raise BizError(code=Code.NOT_FOUND, msg="部分图片不存在，请刷新后重试")
            await run_in_threadpool(_stage_deletions, images, staged)
            await UploadedImage.filter(id__in=ids).delete()
    except BaseException as exc:
        await asyncio.shield(run_in_threadpool(_restore_deletions, staged))
        if isinstance(exc, OSError):
            raise BizError(code=Code.UPLOAD_STORAGE_ERROR, msg="图片删除失败，请检查目录权限") from exc
        raise
    for _, backup in staged:
        try:
            await run_in_threadpool(backup.unlink, missing_ok=True)
        except OSError:
            # The record is already committed as deleted; retain the inaccessible staging file for manual cleanup.
            radar_log("已删除图片的暂存文件清理失败，请检查上传目录", level="ERROR")
    radar_log("删除上传图片", data={"count": len(ids)})
    return len(ids)


async def get_image_path(key: str) -> tuple[Path, str]:
    image = await UploadedImage.get_or_none(key=key)
    if not image:
        raise BizError(code=Code.NOT_FOUND, msg="图片不存在")
    root = Path(image.storage_root).resolve()
    target = (root / image.relative_path).resolve()
    if not target.is_relative_to(root) or not await run_in_threadpool(target.is_file):
        raise BizError(code=Code.NOT_FOUND, msg="图片文件不存在")
    return target, image.media_type
