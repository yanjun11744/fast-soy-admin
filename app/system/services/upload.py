"""本地图片存储：只公开已登记图片，不挂载任意目录。"""

import asyncio
import io
import warnings
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.code import Code
from app.core.config import APP_SETTINGS
from app.core.ctx import CTX_USER_ID
from app.core.exceptions import BizError
from app.system.models.upload import UploadedImage, UploadSetting
from app.system.radar.developer import radar_log
from app.system.schemas.upload import ImageSearch, UploadSettingUpdate

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
    if not target.is_relative_to(root):
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
    return data


async def search_images(query: ImageSearch) -> tuple[int, list[dict]]:
    images = UploadedImage.all()
    if query.name:
        images = images.filter(name__icontains=query.name.strip())
    total = await images.count()
    records = await images.order_by("-id").offset((query.current - 1) * query.size).limit(query.size)
    return total, [await image_data(image) for image in records]


async def get_image_path(key: str) -> tuple[Path, str]:
    image = await UploadedImage.get_or_none(key=key)
    if not image:
        raise BizError(code=Code.NOT_FOUND, msg="图片不存在")
    root = Path(image.storage_root).resolve()
    target = (root / image.relative_path).resolve()
    if not target.is_relative_to(root) or not await run_in_threadpool(target.is_file):
        raise BizError(code=Code.NOT_FOUND, msg="图片文件不存在")
    return target, image.media_type
