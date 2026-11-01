"""
weighbridge_settlement controllers — 基于 CRUDBase 的控制器。
"""

from app.business.weighbridge_settlement.models import SettlementRate, WeighingTicket
from app.utils import CRUDBase

settlement_rate_controller = CRUDBase(model=SettlementRate)
weighing_ticket_controller = CRUDBase(model=WeighingTicket)
