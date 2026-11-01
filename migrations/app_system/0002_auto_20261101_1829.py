from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0001_initial')]

    initial = False

    operations = [
        ops.CreateModel(
            name='UploadSetting',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('storage_root', fields.CharField(default='uploads', description='本地上传目录，相对项目根目录或绝对路径', max_length=1000)),
                ('max_size_mb', fields.IntField(default=5, description='单张图片最大 MB')),
            ],
            options={'table': 'sys_upload_setting', 'app': 'app_system', 'pk_attr': 'id'},
            bases=['BaseModel', 'AuditMixin'],
        ),
        ops.CreateModel(
            name='UploadedImage',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('key', fields.CharField(unique=True, description='随机访问标识', max_length=32)),
                ('name', fields.CharField(description='原始文件名', max_length=255)),
                ('storage_root', fields.CharField(description='上传时的绝对根目录', max_length=1000)),
                ('relative_path', fields.CharField(description='日期和随机文件名', max_length=255)),
                ('media_type', fields.CharField(description='已验证的图片 MIME', max_length=50)),
                ('size', fields.IntField(description='文件字节数')),
                ('width', fields.IntField(description='图片宽度')),
                ('height', fields.IntField(description='图片高度')),
            ],
            options={'table': 'sys_uploaded_image', 'app': 'app_system', 'pk_attr': 'id'},
            bases=['BaseModel', 'AuditMixin'],
        ),
    ]
