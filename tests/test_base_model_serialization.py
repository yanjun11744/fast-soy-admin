"""Regression coverage for date values in model JSON responses."""

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from tortoise import fields

from app.core.base_model import BaseModel
from app.core.base_schema import SuccessExtra
from app.core.config import APP_SETTINGS


class DatedRecord(BaseModel):
    order_due_date = fields.DateField(null=True)
    completed_date = fields.DateField(null=True)
    created_at = fields.DatetimeField(null=True)


@pytest.mark.parametrize("fmt_datetime", [True, False])
@pytest.mark.parametrize("completed_date", [None, date(2026, 10, 31)])
async def test_order_dates_are_json_serializable(fmt_datetime: bool, completed_date: date | None) -> None:
    created_at = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    order = DatedRecord(
        order_due_date=date(2026, 11, 1),
        completed_date=completed_date,
        created_at=created_at,
    )
    # Tortoise normalizes datetime values using its configured timezone.
    created_at = order.created_at

    record = await order.to_dict(fmt_datetime=fmt_datetime)
    response = SuccessExtra(data={"records": [record]}, total=1)
    result = json.loads(response.body)["data"]["records"][0]

    assert result["orderDueDate"] == "2026-11-01"
    assert result["completedDate"] == (completed_date.isoformat() if completed_date else None)
    assert result["createdAt"] == int(created_at.timestamp() * 1000)
    if fmt_datetime:
        assert result["fmtCreatedAt"] == created_at.strftime(APP_SETTINGS.DATETIME_FORMAT)
    else:
        assert "fmtCreatedAt" not in result


async def test_related_dates_are_json_serializable() -> None:
    # Keep relation IO isolated: serialization must also handle values() results.
    relation = Mock()
    relation.all.return_value.values = AsyncMock(return_value=[{"due_date": date(2026, 11, 1), "completed_date": None}])
    model = SimpleNamespace(_meta=SimpleNamespace(db_fields=[], m2m_fields=["items"]), items=relation)

    record = await BaseModel.to_dict(model, m2m=True)
    response = SuccessExtra(data={"records": [record]}, total=1)

    assert json.loads(response.body)["data"]["records"][0]["items"] == [{"dueDate": "2026-11-01", "completedDate": None}]
