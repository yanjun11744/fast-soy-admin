from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0003_auto_20261101_1045')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='WeighingLine',
            name='order',
            field=fields.ForeignKeyField('app_system.Order', source_field='order_id', null=True, description='关联订单', db_constraint=True, to_field='id', related_name='weighing_lines', on_delete=OnDelete.RESTRICT),
        ),
        ops.AlterField(
            model_name='WeighingLine',
            name='order_no',
            field=fields.CharField(null=True, description='订单号快照', max_length=100),
        ),
    ]
