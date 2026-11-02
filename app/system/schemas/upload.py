from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.core.base_schema import CommonIds, PageQueryBase, SchemaBase
from app.core.code import Code
from app.core.exceptions import SchemaValidationError
from app.core.types import SqidId


class UploadSettingUpdate(SchemaBase):
    storage_root: str = Field(min_length=1, max_length=1000)
    max_size_mb: int = Field(5, ge=1, le=20)


class ImageSearch(PageQueryBase):
    name: str | None = Field(None, max_length=255)
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"] | None = None
    created_at_start: datetime | None = None
    created_at_end: datetime | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "ImageSearch":
        if self.created_at_start and self.created_at_end:
            if (self.created_at_start.tzinfo is None) != (self.created_at_end.tzinfo is None) or self.created_at_start > self.created_at_end:
                raise SchemaValidationError(code=Code.REQUEST_VALIDATION, msg="上传时间范围不正确")
        return self


class ImageUpdate(SchemaBase):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[^/\\\x00-\x1f]+$")]


class ImageDelete(CommonIds):
    ids: list[SqidId] = Field(min_length=1, max_length=100)
