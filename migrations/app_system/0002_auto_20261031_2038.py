from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0001_initial')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Order',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('order_no', fields.CharField(unique=True, description='订单号', max_length=100)),
                ('part_no', fields.CharField(db_index=True, description='项目号', max_length=200)),
                ('name', fields.CharField(description='名称', max_length=200)),
                ('unit_weight', fields.DecimalField(description='机内单重/kg（净重）', max_digits=16, decimal_places=6)),
                ('unit', fields.CharField(null=True, description='单位', max_length=50)),
                ('quantity', fields.IntField(null=True, description='数量')),
                ('received_quantity', fields.IntField(null=True, description='入库数量')),
                ('total_weight', fields.DecimalField(null=True, description='合计重量', max_digits=20, decimal_places=6)),
                ('order_due_date', fields.DateField(null=True, description='订单完工期')),
                ('completed_date', fields.DateField(null=True, description='实际完工期')),
                ('process_route', fields.CharField(null=True, description='工艺路线', max_length=500)),
                ('customer', fields.CharField(null=True, description='用户', max_length=200)),
            ],
            options={'table': 'biz_order_management_order', 'app': 'app_system', 'pk_attr': 'id', 'table_description': '订单资料'},
            bases=['BaseModel', 'AuditMixin'],
        ),
    ]
