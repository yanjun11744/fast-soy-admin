"""Exercise generated parent/child wiring as well as the shared export implementation."""

import sys
from base64 import b64decode
from io import BytesIO
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from tortoise.context import tortoise_test_context

from app.cli.generator import gen_api_manage, gen_controllers, gen_schemas
from app.cli.options import BackendFeatureOptions, DataScopeOption
from app.cli.parser import ModelInfo, RelationInfo, parse_models
from app.cli.relations import export_children
from app.cli.web_generator import generate_web
from app.core.exceptions import BizError, BizErrorHandle
from app.utils import encode_id
from tests.test_excel_details import ExportChild, ExportParent


def models(tmp_path: Path) -> list[ModelInfo]:
    source = tmp_path / "models.py"
    source.write_text('''
class ExportParent(BaseModel):
    """主单"""
    number = fields.CharField(max_length=40, unique=True, description="单号")
    name = fields.CharField(max_length=40, description="名称")
    secret = fields.CharField(max_length=40, description="内部资料")

class ExportChild(BaseModel):
    """明细"""
    label = fields.CharField(max_length=40, description="项目")
    amount = fields.DecimalField(max_digits=20, decimal_places=6, description="金额")
    owner_id = fields.IntField(default=1)
    secret = fields.CharField(max_length=40, description="内部资料")
    parent: fields.ForeignKeyRelation[ExportParent] = fields.ForeignKeyField("app_system.ExportParent", related_name="lines", description="主单")
''', encoding="utf-8")
    return parse_models(source)


def test_parent_child_templates_generate_export_and_optional_parent_fields(tmp_path: Path) -> None:
    parsed = models(tmp_path)
    options = BackendFeatureOptions(
        exclude_fields={"ExportParent": ["secret"], "ExportChild": ["secret", "owner_id"]},
        data_scope={"ExportChild": DataScopeOption("owner_id", "owner_id")},
        button_auth_models={model.name for model in parsed},
    )
    backend = gen_api_manage("inventory", parsed, {}, backend_options=options)
    compile(backend, "manage.py", "exec")
    assert "ExcelDetail(sheet_name='明细_1', resource=lambda: export_child_crud, parent_field='parent_id')" in backend
    assert "excel_scope_filter=_export_child_excel_scope" in backend
    assert "fields=('label', 'amount', 'parent_id')" in backend
    assert 'require_buttons("B_INVENTORY_EXPORT_PARENT_EXPORT")' in backend
    generate_web(
        tmp_path, "inventory", "库存", parsed, list_fields_map={}, search_fields_map={},
        button_auth_models=options.button_auth_models, backend_options=options,
    )
    parent = (tmp_path / "src/views/inventory/export-parent/index.vue").read_text()
    assert 'parentFields => fetchExportExportParent({ ...searchParams, parentFields })' in parent
    assert '(ids, parentFields) => fetchExportExportParent({ ...searchParams, ids, parentFields })' in parent
    option_line = next(line for line in parent.splitlines() if ":export-parent-fields=" in line)
    assert "name: 'number'" in option_line and "name: 'name'" in option_line
    assert "secret" not in option_line
    child = (tmp_path / "src/views/inventory/export-child/index.vue").read_text()
    assert ":export-parent-fields=" not in child
    service = (tmp_path / "src/service/api/inventory-manage.ts").read_text()
    assert "ExportParentSearchParams & { ids?: string[]; parentFields?: string[] }" in service


def test_export_relationship_detection_excludes_unrelated_self_and_unreadable_models(tmp_path: Path) -> None:
    parent, child = models(tmp_path)
    child.relations.extend([
        RelationInfo("other", "ForeignKeyField", "app_inventory.ExportParent"),
        RelationInfo("external", "ForeignKeyField", "app_other.ExportParent"),
        RelationInfo("many", "ManyToManyField", "app_system.ExportParent"),
    ])
    parent.relations.append(RelationInfo("self", "ForeignKeyField", "app_system.ExportParent"))
    assert [relation.name for _, relation in export_children("inventory", parent, [parent, child], BackendFeatureOptions())] == ["parent", "other"]
    assert export_children("inventory", parent, [parent, child], BackendFeatureOptions(enable_routes={child.name: {"get"}})) == []
    options = BackendFeatureOptions(exclude_fields={child.name: [field.name for field in child.schema_fields] + [f"{relation.name}_id" for relation in child.relations]})
    assert export_children("inventory", parent, [parent, child], options) == []


@pytest.mark.asyncio(loop_scope="session")
async def test_generated_api_exports_real_related_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = models(tmp_path)
    module_name = "_export_codegen_test"
    prefix = f"app.business.{module_name}"
    package = ModuleType(prefix)
    package.__path__ = []
    monkeypatch.setitem(sys.modules, prefix, package)
    model_module = ModuleType(f"{prefix}.models")
    model_module.ExportParent = ExportParent
    model_module.ExportChild = ExportChild
    monkeypatch.setitem(sys.modules, model_module.__name__, model_module)
    options = BackendFeatureOptions(exclude_fields={"ExportParent": ["secret"], "ExportChild": ["secret", "owner_id"]})
    sources = {
        "schemas": gen_schemas(module_name, parsed),
        "controllers": gen_controllers(module_name, parsed),
        "api.manage": gen_api_manage(module_name, parsed, {}, backend_options=options),
    }
    async with tortoise_test_context(modules=["tests.test_excel_details"], app_label="app_system", connection_label="generated", use_tz=False):
        for name, source in sources.items():
            module = ModuleType(f"{prefix}.{name}")
            monkeypatch.setitem(sys.modules, module.__name__, module)
            exec(compile(source, name, "exec"), module.__dict__)
        api = FastAPI()
        api.add_exception_handler(BizError, BizErrorHandle)
        api.include_router(module.router)
        parent = await ExportParent.create(number="000123", name="test")
        other = await ExportParent.create(number="other", name="test")
        await ExportChild.create(parent_id=parent.pk, label="=text", amount="1.123456")
        await ExportChild.create(parent_id=other.pk, label="unselected", amount="9")
        async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
            response = await client.post("/export_parents/export", json={"ids": [encode_id(parent.pk)], "parentFields": ["number"]})
        assert response.json()["code"] == "0000"
        workbook = load_workbook(BytesIO(b64decode(response.json()["data"]["content"])))
        try:
            assert workbook.sheetnames == ["Data", "明细_1"]
            assert list(workbook["明细_1"].values) == [
                ("父表：单号", "项目", "金额", "主单"),
                ("000123", "=text", "1.123456", encode_id(parent.pk)),
            ]
            assert workbook["明细_1"]["B2"].data_type == "s"
        finally:
            workbook.close()
