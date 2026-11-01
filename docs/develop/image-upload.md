# 本地图片上传、显示与浏览

## 系统管理

执行新增迁移，在应用下次启动完成菜单初始化后，进入 **系统管理 → 上传管理**。

- 默认目录为项目根目录下的 `uploads/`，默认单张上限 5 MB；页面可设置目录和 1～20 MB 上限。
- 相对路径以**后端项目根目录**为起点，也可填写服务器绝对路径；保存时验证目录可写。
- 配置保存在 `sys_upload_setting`，文件索引保存在 `sys_uploaded_image`，图片内容保存在本地文件系统。
- 每张图片记录上传时的目录；切换目录只影响后续上传，旧图仍从原目录读取。请保留原目录。
- 以随机名称按 `年/月/日` 分目录保存，不采用客户端提供的路径。
- 使用分页表格展示缩略图、文件名、格式、大小、尺寸、上传人和上传时间，支持按文件名、格式及上传时间筛选。
- 支持上传、详情、重命名、单条/批量删除和复制链接；重命名只改显示名称，链接保持不变。
- `.gitignore` 排除项目根目录的 `uploads/`，不跟踪上传图片；如将存储目录改到仓库内的其他位置，也应为该目录添加忽略规则。
- 业务表保存返回的相对 URL。组件显示时解析当前代理、生产 API 前缀或独立 API 域名。

图片是**公开资源**：有随机链接即可查看，不适用于私密文件。上传和后台浏览/配置仍需要登录及相应权限。后端验证实际图片内容、大小和像素上限，支持 JPEG/PNG/GIF/WebP，不允许 SVG/HTML。

备份时同时备份数据库和所有使用过的上传目录。容器需要挂载持久化目录；反向代理的请求大小上限需允许配置的图片大小。本次不修改部署配置。

## 组件

```vue
<script setup lang="ts">
import { ref } from 'vue';
import ImageUpload from '@/components/advanced/image-upload.vue';
import ImagePreview from '@/components/advanced/image-preview.vue';

const cover = ref('');
const gallery = ref<string[]>([]);
const uploading = ref(false);
</script>

<template>
  <div>
    <ImageUpload v-model:value="cover" v-model:busy="uploading" :limit="1" />
    <ImageUpload v-model:value="gallery" value-type="array" :limit="5" />
    <ImagePreview :value="gallery" :width="64" :height="64" />
  </div>
</template>
```

`value` 支持路径字符串、逗号分隔字符串、字符串数组、`null`。字符串模型返回逗号分隔字符串；数组模型设置 `value-type="array"`。`limit` 默认 5，`max-size-mb` 可缩小系统上限，`disabled` 开启只读模式。

组件支持多选、回显、进度、失败重试、移除和顺序调整。组件内移除只解除当前表单引用，**不会删除磁盘文件**。上传后取消表单的文件仍保留在图片库。

后台“删除”会永久删除文件及索引记录，页面确认框会提示引用影响。现有业务引用不会自动替换，浏览器已缓存的旧图可能在缓存过期后才消失。批量删除一次最多 100 项，任意记录不存在时整批不执行。删除期间先在同目录暂存文件，数据库操作失败则恢复文件；提交后清理暂存文件，清理失败会产生 Radar 错误记录。没有自动清理未引用图片的任务。

提交时用 `v-model:busy` 禁用保存。多个组件分别记录 busy，再取任一为真。组件卸载、切换模型或移除待上传项时取消请求，迟到结果不会覆盖新模型。

## 代码生成

沿用 `just cli-crud` / `just cli-gen-web`，无需新增参数：

```python
from tortoise import fields
from app.utils import AuditMixin, BaseModel

class Product(BaseModel, AuditMixin):
    """商品"""
    name = fields.CharField(max_length=100, description="名称")
    cover = fields.CharField(max_length=500, null=True, description="封面")
    photos = fields.TextField(null=True, description="商品图片")
    gallery = fields.JSONField(null=True, description="详情相册 [images]")
    certificate = fields.CharField(max_length=500, null=True, description="证书 [image]")

    class Meta:
        table = "biz_inventory_product"
```

- 单图名称：`image` / `photo` / `picture` / `avatar` / `cover` / `logo`，支持业务前缀和 `_url` 后缀，例如 `product_cover_url`。
- 多图名称：`images` / `photos` / `pictures`，支持业务前缀和 `_urls` 后缀。
- 其他 CharField/TextField/JSONField 用 description 的 `[image]` / `[images]` 声明；标记优先于名称，不出现在生成的前端标题里。
- CharField/TextField 按字符串持久化，多图建议 TextField，避免总长度超过 CharField 限制。JSONField 对应后端 `list[str]`、前端 `string[]`。
- 列表生成 `ImagePreview`，编辑抽屉生成 `ImageUpload`，上传中禁用保存；图片字段不进入默认搜索。
- 生成菜单附加共用 `B_SYSTEM_UPLOAD_CREATE` 按钮。给业务角色授权该按钮即可上传，无需授予全局图片库或目录配置权限。
- 浏览器代码生成页也识别上述名称和标记。请先修改 `models.py` 再解析；页面辅助配置和生成 CLI 命令。

## 接口与权限

所有接口以 `/api/v1` 为前缀。

| 接口 | 权限 | 用途 |
|---|---|---|
| `GET /system-manage/uploads/options` | 登录 | 上传限制 |
| `POST /system-manage/uploads/images` | 登录 + `B_SYSTEM_UPLOAD_CREATE` | multipart 字段 `file` 上传 |
| `GET /system-manage/uploads/settings` | API 权限 | 获取目录配置 |
| `PATCH /system-manage/uploads/settings` | API 权限 + `B_SYSTEM_UPLOAD_CONFIG` | 更新配置 |
| `POST /system-manage/uploads/search` | API 权限 | 文件名搜索及分页 |
| `GET /system-manage/uploads/images/{id}` | API 权限 | 图片详情 |
| `PATCH /system-manage/uploads/images/{id}` | API 权限 + `B_SYSTEM_UPLOAD_EDIT` | 修改显示名称 |
| `DELETE /system-manage/uploads/images/{id}` | API 权限 + `B_SYSTEM_UPLOAD_DELETE` | 删除单张图片及记录 |
| `DELETE /system-manage/uploads/images` | API 权限 + `B_SYSTEM_UPLOAD_DELETE` | 批量删除，body 为 `ids` 数组 |
| `GET /system-manage/uploads/content/{key}` | 公开 | 返回登记图片，不挂载任意静态目录 |

迁移文件 `migrations/app_system/0002_auto_20261101_1829.py` 仅创建两张新表，不修改现有业务字段。[SQL 预览](../ops/image-upload-migration.sql)。检查 `just dbhistory`、确认 SQL 和备份后执行 `just migrate`。如历史包含仓库已不存在的旧迁移，不要清空历史、删库或重建已有表来绕过。

交互参考 [RuoYi ImageUpload](https://github.com/yangzongzhuan/RuoYi-Vue/blob/master/ruoyi-ui/src/components/ImageUpload/index.vue)，按本项目 Vue 3、Naive UI、请求与权限体系重新实现。
