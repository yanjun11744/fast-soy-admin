from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('app_system', '0002_auto_20261031_2038')]

    initial = False

    operations = [
        ops.CreateModel(
            name='SettlementRate',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('process_name', fields.CharField(unique=True, description='工序名称', max_length=100)),
                ('price', fields.DecimalField(description='含税招采价格（元/kg）', max_digits=10, decimal_places=4)),
                ('enabled', fields.BooleanField(default=True, description='是否启用')),
            ],
            options={'table': 'biz_settlement_rate', 'app': 'app_system', 'pk_attr': 'id', 'table_description': '工序招采价格'},
            bases=['BaseModel', 'AuditMixin'],
        ),
        ops.CreateModel(
            name='WeighingTicket',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('ticket_no', fields.CharField(unique=True, description='磅单编号', max_length=100)),
                ('weighing_date', fields.DateField(db_index=True, description='过磅日期')),
                ('weight', fields.DecimalField(description='实际过磅重量/kg', max_digits=16, decimal_places=3)),
                ('rate', fields.ForeignKeyField('app_system.SettlementRate', source_field='rate_id', description='工序招采价格', db_constraint=True, to_field='id', related_name='tickets', on_delete=OnDelete.RESTRICT)),
                ('process', fields.CharField(description='工序名称快照', max_length=100)),
                ('price', fields.DecimalField(description='含税价格快照（元/kg）', max_digits=10, decimal_places=4)),
                ('total_amount', fields.DecimalField(description='含税总金额/元', max_digits=20, decimal_places=2)),
                ('is_settled', fields.BooleanField(default=False, description='是否已结算')),
                ('revision', fields.IntField(default=1, description='修订版本')),
            ],
            options={'table': 'biz_settlement_ticket', 'app': 'app_system', 'pk_attr': 'id', 'table_description': '磅单信息'},
            bases=['BaseModel', 'AuditMixin'],
        ),
        ops.CreateModel(
            name='WeighingLine',
            fields=[
                ('created_by', fields.CharField(null=True, description='创建人', max_length=64)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_by', fields.CharField(null=True, description='更新人', max_length=64)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('id', fields.IntField(generated=True, primary_key=True, unique=True, db_index=True)),
                ('ticket', fields.ForeignKeyField('app_system.WeighingTicket', source_field='ticket_id', description='所属磅单', db_constraint=True, to_field='id', related_name='lines', on_delete=OnDelete.CASCADE)),
                ('order', fields.ForeignKeyField('app_system.Order', source_field='order_id', description='关联订单', db_constraint=True, to_field='id', related_name='weighing_lines', on_delete=OnDelete.RESTRICT)),
                ('position', fields.IntField(description='明细顺序')),
                ('order_no', fields.CharField(description='订单号快照', max_length=100)),
                ('part_no', fields.CharField(description='项目号快照', max_length=200)),
                ('name', fields.CharField(description='名称快照', max_length=200)),
                ('unit_weight', fields.DecimalField(description='机内单重快照/kg', max_digits=16, decimal_places=6)),
                ('quantity', fields.IntField(description='实际过磅数量')),
                ('theoretical_weight', fields.DecimalField(description='机内合重/kg', max_digits=24, decimal_places=6)),
                ('allocated_weight', fields.DecimalField(description='分摊过磅重量/kg', max_digits=16, decimal_places=3)),
                ('amount', fields.DecimalField(description='含税结算金额/元', max_digits=20, decimal_places=2)),
                ('tax_unit_price', fields.DecimalField(description='含税单价（元/件）', max_digits=20, decimal_places=6)),
            ],
            options={'table': 'biz_settlement_line', 'app': 'app_system', 'unique_together': (('ticket', 'position'), ('ticket', 'order')), 'pk_attr': 'id', 'table_description': '磅单结算明细'},
            bases=['BaseModel', 'AuditMixin'],
        ),
    ]
