from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from app.core.base_schema import Success, SuccessExtra
from app.core.code import Code
from app.core.dependency import DependAuth, DependPermission, require_buttons
from app.core.exceptions import BizError
from app.core.types import SqidPath
from app.system.schemas.upload import ImageDelete, ImageSearch, ImageUpdate, UploadSettingUpdate
from app.system.services.upload import delete_images, get_image, get_image_path, get_upload_setting, save_image, search_images, update_image, update_upload_setting

router = APIRouter()


@router.get("/uploads/options", dependencies=[DependAuth], summary="获取图片上传限制")
async def upload_options() -> Success:
    setting = await get_upload_setting()
    return Success(data={"maxSizeMb": setting.max_size_mb, "extensions": ["jpg", "jpeg", "png", "gif", "webp"]})


@router.get("/uploads/settings", dependencies=[DependPermission], summary="获取本地上传配置")
async def upload_settings() -> Success:
    setting = await get_upload_setting()
    return Success(data={"storageRoot": setting.storage_root, "maxSizeMb": setting.max_size_mb})


@router.patch("/uploads/settings", dependencies=[DependPermission, require_buttons("B_SYSTEM_UPLOAD_CONFIG")], summary="更新本地上传配置")
async def configure_uploads(obj: UploadSettingUpdate) -> Success:
    setting = await update_upload_setting(obj)
    return Success(data={"storageRoot": setting.storage_root, "maxSizeMb": setting.max_size_mb})


@router.post("/uploads/images", dependencies=[DependAuth, require_buttons("B_SYSTEM_UPLOAD_CREATE")], summary="上传本地图片")
async def upload_image(file: Annotated[UploadFile, File()]) -> Success:
    try:
        setting = await get_upload_setting()
        limit = setting.max_size_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise BizError(code=Code.UPLOAD_TOO_LARGE, msg=f"图片不能超过 {setting.max_size_mb} MB")
        return Success(data=await save_image(content, file.filename or "image", setting))
    finally:
        await file.close()


@router.post("/uploads/search", dependencies=[DependPermission], summary="浏览上传图片")
async def list_images(obj: ImageSearch) -> SuccessExtra:
    total, records = await search_images(obj)
    return SuccessExtra(data={"records": records}, total=total, current=obj.current, size=obj.size)


@router.get("/uploads/images/{item_id}", dependencies=[DependPermission], summary="上传图片详情")
async def image_detail(item_id: SqidPath) -> Success:
    return Success(data=await get_image(item_id))


@router.patch("/uploads/images/{item_id}", dependencies=[DependPermission, require_buttons("B_SYSTEM_UPLOAD_EDIT")], summary="重命名上传图片")
async def rename_image(item_id: SqidPath, obj: ImageUpdate) -> Success:
    return Success(data=await update_image(item_id, obj))


@router.delete("/uploads/images/{item_id}", dependencies=[DependPermission, require_buttons("B_SYSTEM_UPLOAD_DELETE")], summary="删除上传图片")
async def delete_image(item_id: SqidPath) -> Success:
    return Success(data={"deletedCount": await delete_images([item_id])})


@router.delete("/uploads/images", dependencies=[DependPermission, require_buttons("B_SYSTEM_UPLOAD_DELETE")], summary="批量删除上传图片")
async def batch_delete_images(obj: ImageDelete) -> Success:
    return Success(data={"deletedCount": await delete_images(obj.ids)})


@router.get("/uploads/content/{key}", summary="显示公开图片", include_in_schema=False)
async def image_content(key: str) -> FileResponse:
    path, media_type = await get_image_path(key)
    return FileResponse(path, media_type=media_type, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=86400"})
