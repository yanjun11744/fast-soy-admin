"""Order Excel headers use business names; weight units belong to the UI."""

from decimal import Decimal

import pytest

from app.business.order_management.api.manage import order_crud
from app.business.order_management.schemas import OrderCreate
from app.core.excel import read_excel, write_excel


@pytest.mark.parametrize('weight_headers', [('净重', '毛重'), ('netWeight', 'grossWeight'), ('net_weight', 'gross_weight')])
def test_order_import_recognizes_weight_headers_without_units(weight_headers: tuple[str, str]) -> None:
    config = order_crud.excel
    assert config is not None
    content = write_excel(['订单号', '项目号', '名称', *weight_headers], [['IMPORT-1', 'PART-1', '示例', '1.123456', '2.654321']])
    rows = read_excel(content, OrderCreate, config)
    assert rows[0].net_weight == Decimal('1.123456')
    assert rows[0].gross_weight == Decimal('2.654321')


def test_order_template_and_export_use_weight_headers_without_units() -> None:
    config = order_crud.excel
    assert config is not None
    headers, _ = config.resolve(OrderCreate)
    assert headers[config.fields.index('net_weight')] == '净重'
    assert headers[config.fields.index('gross_weight')] == '毛重'
    data = OrderCreate(order_no='EXPORT-1', part_no='PART-1', name='示例', net_weight=Decimal('1.123456'), gross_weight=Decimal('2.654321'))
    content = write_excel(headers, [[getattr(data, name) for name in config.fields]])
    imported = read_excel(content, OrderCreate, config)[0]
    assert imported == data
