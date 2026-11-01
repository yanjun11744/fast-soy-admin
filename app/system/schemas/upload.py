from pydantic import Field

from app.core.base_schema import PageQueryBase, SchemaBase


class UploadSettingUpdate(SchemaBase):
    storage_root: str = Field(min_length=1, max_length=1000)
    max_size_mb: int = Field(5, ge=1, le=20)


class ImageSearch(PageQueryBase):
    name: str | None = Field(None, max_length=255)
