"""Deterministic Decimal settlement calculations, shared by preview and persistence."""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from app.utils import BizError


def calculate(weight: Decimal, price: Decimal, lines: list[dict[str, Any]]) -> tuple[Decimal, list[dict[str, Any]]]:
    with localcontext() as ctx:
        ctx.prec = 60
        weight = weight.quantize(Decimal(".001"), rounding=ROUND_HALF_UP)
        price = price.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
        if weight <= 0 or price <= 0 or not lines:
            raise BizError(code="4601", msg="重量、价格及明细必须有效且大于零")
        total_amount = (weight * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        if total_amount >= Decimal("1e18"):
            raise BizError(code="4601", msg="结算金额超出存储范围")
        result = []
        for position, line in enumerate(lines, 1):
            row = dict(line)
            if row.get("gross_weight") is None:
                raise BizError(code="4601", msg="请补填明细毛重后重新保存磅单")
            unit = Decimal(str(row["gross_weight"])).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)
            quantity = row["quantity"]
            if not unit.is_finite() or unit <= 0 or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
                raise BizError(code="4601", msg="明细毛重及实际数量必须大于零")
            row.update(position=position, gross_weight=unit, theoretical_weight=unit * quantity)
            if row["theoretical_weight"] >= Decimal("1e18"):
                raise BizError(code="4601", msg="理论重量超出存储范围")
            result.append(row)
        total = sum((row["theoretical_weight"] for row in result), Decimal(0))
        remaining_weight, remaining_amount = weight, total_amount
        for index, row in enumerate(result):
            last = index == len(result) - 1
            # Clamp to the remainder for tiny tickets with many lines: never create a negative final allocation.
            allocated = remaining_weight if last else min(remaining_weight, (weight * row["theoretical_weight"] / total).quantize(Decimal(".001"), rounding=ROUND_HALF_UP))
            amount = remaining_amount if last else min(remaining_amount, (allocated * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
            row.update(allocated_weight=allocated, amount=amount, tax_unit_price=(amount / row["quantity"]).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP))
            if row["tax_unit_price"] >= Decimal("1e14"):
                raise BizError(code="4601", msg="每件单价超出存储范围")
            remaining_weight -= allocated
            remaining_amount -= amount
        return total_amount, result
