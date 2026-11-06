from tortoise import migrations
from tortoise.migrations import operations as ops
from orjson import loads
from tortoise.fields.data import JSON_DUMPS
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0006_auto_20261102_1041')]

    initial = False

    operations = [
        ops.AddField(
            model_name='WeighingTicket',
            name='images',
            field=fields.JSONField(null=True, description='磅单图片 [images]', encoder=JSON_DUMPS, decoder=loads),
        ),
    ]
