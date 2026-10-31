"""Date search generation must agree across schema, query and frontend."""

from datetime import date, datetime

import pytest
from tortoise.expressions import Q

from app.cli.generator import gen_api_manage, gen_schemas
from app.cli.options import BackendFeatureOptions, DataScopeOption, resolve_field_map
from app.cli.parser import FieldInfo, ModelInfo
from app.cli.prompts import (
    PromptChoice,
    default_frontend_search_field_names,
    exact_field_candidates,
    fuzzy_field_candidates,
)
from app.cli.web_generator import gen_typings_dts, gen_view_drawer, gen_view_index, gen_view_search
from app.core.crud import CRUDBase
from app.system.models.dictionary import Dictionary


@pytest.fixture
def dated_model() -> ModelInfo:
    return ModelInfo(name="Shipment", cn_name="发货", fields=[
        FieldInfo("name", "CharField", "str", max_length=100),
        FieldInfo("due_date", "DateField", "date", description="交付日期", required=False),
        FieldInfo("sent_at", "DatetimeField", "datetime", description="发货时间", required=False),
    ])


def test_dates_are_default_range_candidates(dated_model: ModelInfo) -> None:
    selected = resolve_field_map(
        [dated_model], (), fuzzy_field_candidates, defaults_when_missing=True, option_name="--contains"
    )
    assert selected == {"Shipment": ["name", "due_date", "sent_at"]}
    assert [field.name for field in exact_field_candidates(dated_model)] == ["name"]
    defaults = default_frontend_search_field_names([{"Shipment": ["name"]}])
    assert defaults(dated_model, [PromptChoice(f.name) for f in dated_model.schema_fields]) == ["due_date", "sent_at", "name"]


@pytest.mark.parametrize("override", [False, True])
def test_backend_generates_ranges_for_standard_and_override_queries(dated_model: ModelInfo, override: bool) -> None:
    options = BackendFeatureOptions(data_scope={"Shipment": DataScopeOption()}) if override else None
    source = gen_api_manage(
        "logistics", [dated_model], {"Shipment": ["name", "due_date"]}, {"Shipment": ["sent_at"]}, backend_options=options
    )
    compile(source, "generated_api.py", "exec")
    assert "contains_fields=['name']" in source
    assert "exact_fields=['sent_at']" not in source
    assert source.count("range_fields=['due_date', 'sent_at']") == (2 if override else 1)
    # Dates also work without any text/exact fields configured.
    assert "SearchFieldConfig(range_fields=['due_date', 'sent_at'])" in gen_api_manage("logistics", [dated_model], {}, {})


@pytest.mark.parametrize("payload,expected", [
    ({"dueDateStart": "2026-11-01", "dueDateEnd": "2026-11-30"}, {"due_date__gte": date(2026, 11, 1), "due_date__lte": date(2026, 11, 30)}),
    ({"sentAtStart": "2026-11-01 10:00:00"}, {"sent_at__gte": datetime(2026, 11, 1, 10)}),
    ({"dueDateStart": None, "dueDateEnd": None}, {}),
])
def test_generated_schema_drives_range_filters(dated_model: ModelInfo, payload: dict, expected: dict) -> None:
    namespace = {}
    exec(gen_schemas("logistics", [dated_model]), namespace)
    schema = namespace["ShipmentSearch"].model_validate(payload)
    query = CRUDBase(Dictionary).build_search(schema, range_fields=["due_date", "sent_at"])
    def collect_filters(node: Q) -> dict:
        filters = dict(node.filters)
        for child in node.children:
            filters.update(collect_filters(child))
        return filters

    assert collect_filters(query) == expected


def test_frontend_generates_range_controls_and_reset_parameters(dated_model: ModelInfo) -> None:
    fields = ["name", "due_date", "sent_at"]
    typings = gen_typings_dts("logistics", [dated_model], {"Shipment": fields})
    search = gen_view_search("logistics", dated_model, fields)
    index = gen_view_index("logistics", dated_model, fields, search_field_names=fields)
    for camel in ("dueDate", "sentAt"):
        assert f"{camel}Start?: string;" in typings
        assert f"{camel}End?: string;" in typings
        assert f"{camel}Start: null," in index
        assert f"{camel}End: null," in index
        assert f'v-model:formatted-value="{camel}Range"' in search
        assert f"model.value.{camel}Start = value?.[0] ?? null;" in search
        assert f"model.value.{camel}End = value?.[1] ?? null;" in search
    assert 'type="daterange" value-format="yyyy-MM-dd"' in search
    assert 'type="datetimerange" value-format="yyyy-MM-dd HH:mm:ss"' in search
    assert 'v-model:value="model.name"' in search
    assert 'v-model:formatted-value="model.dueDate"' in gen_view_drawer("logistics", dated_model)
