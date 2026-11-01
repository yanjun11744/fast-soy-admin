# pyright: reportIncompatibleVariableOverride=false
"""
weighbridge_settlement — 请求/响应 Schema。
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.utils import Int32, PageQueryBase, SchemaBase, SqidId

# ============================================================
# 工序招采价格
# ============================================================


class SettlementRateBase(SchemaBase):
    process_name: Annotated[str, Field(max_length=100)] | None = Field(None, title="工序名称")
    price: Decimal | None = Field(None, title="含税招采价格（元/kg）")
    enabled: bool | None = Field(None, title="是否启用")


class SettlementRateCreate(SettlementRateBase):
    process_name: Annotated[str, Field(max_length=100)] = Field(title="工序名称")
    price: Decimal = Field(title="含税招采价格（元/kg）")


class SettlementRateUpdate(SettlementRateBase): ...


class SettlementRateSearch(SettlementRateBase, PageQueryBase):
    pass


# ============================================================
# 磅单信息
# ============================================================


class WeighingTicketBase(SchemaBase):
    ticket_no: Annotated[str, Field(max_length=100)] | None = Field(None, title="磅单编号")
    weighing_date: date | None = Field(None, title="过磅日期")
    weight: Decimal | None = Field(None, title="实际过磅重量/kg")
    process: Annotated[str, Field(max_length=100)] | None = Field(None, title="工序名称快照")
    price: Decimal | None = Field(None, title="含税价格快照（元/kg）")
    total_amount: Decimal | None = Field(None, title="含税总金额/元")
    is_settled: bool | None = Field(None, title="是否已结算")
    revision: Int32 | None = Field(None, title="修订版本")
    rate_id: SqidId | None = Field(None, title="工序招采价格")


class WeighingTicketCreate(WeighingTicketBase):
    ticket_no: Annotated[str, Field(max_length=100)] = Field(title="磅单编号")
    weighing_date: date = Field(title="过磅日期")
    weight: Decimal = Field(title="实际过磅重量/kg")
    process: Annotated[str, Field(max_length=100)] = Field(title="工序名称快照")
    price: Decimal = Field(title="含税价格快照（元/kg）")
    total_amount: Decimal = Field(title="含税总金额/元")
    rate_id: SqidId = Field(title="工序招采价格")


class WeighingTicketUpdate(WeighingTicketBase): ...


class WeighingTicketSearch(WeighingTicketBase, PageQueryBase):
    weighing_date_start: date | None = Field(None, title="过磅日期开始")
    weighing_date_end: date | None = Field(None, title="过磅日期结束")
