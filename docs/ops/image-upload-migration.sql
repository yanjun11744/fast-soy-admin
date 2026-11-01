BEGIN;
--
-- Create model UploadSetting
--
CREATE TABLE "sys_upload_setting" (
    "created_by" VARCHAR(64),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_by" VARCHAR(64),
    "updated_at" TIMESTAMPTZ NOT NULL,
    "id" SERIAL NOT NULL PRIMARY KEY,
    "storage_root" VARCHAR(1000) NOT NULL,
    "max_size_mb" INT NOT NULL
);
COMMENT ON COLUMN "sys_upload_setting"."created_by" IS '创建人';
COMMENT ON COLUMN "sys_upload_setting"."created_at" IS '创建时间';
COMMENT ON COLUMN "sys_upload_setting"."updated_by" IS '更新人';
COMMENT ON COLUMN "sys_upload_setting"."updated_at" IS '更新时间';
COMMENT ON COLUMN "sys_upload_setting"."storage_root" IS '本地上传目录，相对项目根目录或绝对路径';
COMMENT ON COLUMN "sys_upload_setting"."max_size_mb" IS '单张图片最大 MB';
--
-- Create model UploadedImage
--
CREATE TABLE "sys_uploaded_image" (
    "created_by" VARCHAR(64),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_by" VARCHAR(64),
    "updated_at" TIMESTAMPTZ NOT NULL,
    "id" SERIAL NOT NULL PRIMARY KEY,
    "key" VARCHAR(32) NOT NULL UNIQUE,
    "name" VARCHAR(255) NOT NULL,
    "storage_root" VARCHAR(1000) NOT NULL,
    "relative_path" VARCHAR(255) NOT NULL,
    "media_type" VARCHAR(50) NOT NULL,
    "size" INT NOT NULL,
    "width" INT NOT NULL,
    "height" INT NOT NULL
);
COMMENT ON COLUMN "sys_uploaded_image"."created_by" IS '创建人';
COMMENT ON COLUMN "sys_uploaded_image"."created_at" IS '创建时间';
COMMENT ON COLUMN "sys_uploaded_image"."updated_by" IS '更新人';
COMMENT ON COLUMN "sys_uploaded_image"."updated_at" IS '更新时间';
COMMENT ON COLUMN "sys_uploaded_image"."key" IS '随机访问标识';
COMMENT ON COLUMN "sys_uploaded_image"."name" IS '原始文件名';
COMMENT ON COLUMN "sys_uploaded_image"."storage_root" IS '上传时的绝对根目录';
COMMENT ON COLUMN "sys_uploaded_image"."relative_path" IS '日期和随机文件名';
COMMENT ON COLUMN "sys_uploaded_image"."media_type" IS '已验证的图片 MIME';
COMMENT ON COLUMN "sys_uploaded_image"."size" IS '文件字节数';
COMMENT ON COLUMN "sys_uploaded_image"."width" IS '图片宽度';
COMMENT ON COLUMN "sys_uploaded_image"."height" IS '图片高度';
COMMIT;
