from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0005_auto_20261102_1022')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Order',
            name='gross_weight',
            field=fields.DecimalField(null=True, description='毛重', max_digits=16, decimal_places=6),
        ),
        ops.AlterField(
            model_name='Order',
            name='net_weight',
            field=fields.DecimalField(description='净重', max_digits=16, decimal_places=6),
        ),
        ops.AlterField(
            model_name='WeighingLine',
            name='gross_weight',
            field=fields.DecimalField(null=True, description='毛重快照', max_digits=16, decimal_places=6),
        ),
        ops.AlterField(
            model_name='WeighingLine',
            name='net_weight',
            field=fields.DecimalField(description='净重快照', max_digits=16, decimal_places=6),
        ),
    ]
