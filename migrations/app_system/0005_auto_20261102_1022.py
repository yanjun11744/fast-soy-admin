from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0002_auto_20261101_1829'), ('app_system', '0004_auto_20261101_1059')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Order',
            name='gross_weight',
            field=fields.DecimalField(null=True, description='毛重/kg', max_digits=16, decimal_places=6),
        ),
        ops.RenameField(model_name='Order', old_name='unit_weight', new_name='net_weight'),
        ops.AlterField(
            model_name='Order',
            name='net_weight',
            field=fields.DecimalField(description='净重/kg', max_digits=16, decimal_places=6),
        ),
        ops.AddField(
            model_name='WeighingLine',
            name='gross_weight',
            field=fields.DecimalField(null=True, description='毛重快照/kg', max_digits=16, decimal_places=6),
        ),
        ops.RenameField(model_name='WeighingLine', old_name='unit_weight', new_name='net_weight'),
        ops.AlterField(
            model_name='WeighingLine',
            name='net_weight',
            field=fields.DecimalField(description='净重快照/kg', max_digits=16, decimal_places=6),
        ),
    ]
