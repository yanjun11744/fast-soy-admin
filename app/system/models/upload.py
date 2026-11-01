# pyright: reportIncompatibleVariableOverride=false
"""本地图片配置与文件索引。每条记录保留上传时的根目录。"""

from tortoise import fields

from app.core.base_model import AuditMixin, BaseModel


class UploadSetting(BaseModel, AuditMixin):
    id = fields.IntField(primary_key=True)
    storage_root = fields.CharField(max_length=1000, default="uploads", description="本地上传目录，相对项目根目录或绝对路径")
    max_size_mb = fields.IntField(default=5, description="单张图片最大 MB")

    class Meta:
        table = "sys_upload_setting"


class UploadedImage(BaseModel, AuditMixin):
    id = fields.IntField(primary_key=True)
    key = fields.CharField(max_length=32, unique=True, description="随机访问标识")
    name = fields.CharField(max_length=255, description="原始文件名")
    storage_root = fields.CharField(max_length=1000, description="上传时的绝对根目录")
    relative_path = fields.CharField(max_length=255, description="日期和随机文件名")
    media_type = fields.CharField(max_length=50, description="已验证的图片 MIME")
    size = fields.IntField(description="文件字节数")
    width = fields.IntField(description="图片宽度")
    height = fields.IntField(description="图片高度")

    class Meta:
        table = "sys_uploaded_image"
        ordering = ["-id"]


__all__ = ["UploadSetting", "UploadedImage"]
