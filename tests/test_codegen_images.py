from pathlib import Path

from app.cli.generator import gen_init_data, gen_schemas
from app.cli.parser import parse_models
from app.cli.prompts import exact_field_candidates, fuzzy_field_candidates
from app.cli.web_generator import gen_typings_dts, gen_view_drawer, gen_view_index


def test_image_fields_generate_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "models.py"
    source.write_text('''
class Product(BaseModel):
    name = fields.CharField(max_length=100, description="名称")
    cover = fields.CharField(max_length=500, null=True, description="封面")
    gallery = fields.JSONField(null=True, description="相册 [images]")
    photos = fields.TextField(null=True, description="图片")
    attachment = fields.TextField(null=True, description="附件")
''', encoding="utf-8")
    model = parse_models(source)[0]
    assert [f.image_kind for f in model.schema_fields] == [None, "single", "multiple", "multiple", None]
    assert [f.name for f in fuzzy_field_candidates(model)] == ["name", "attachment"]
    assert [f.name for f in exact_field_candidates(model)] == ["name"]
    schema = gen_schemas("inventory", [model])
    namespace = {}
    exec(schema, namespace)
    item = namespace["ProductCreate"].model_validate({"name": "test", "gallery": ["/system-manage/uploads/content/key"]})
    assert isinstance(item.gallery, list)
    assert "gallery: string[]" in gen_typings_dts("inventory", [model], {})
    drawer = gen_view_drawer("inventory", model)
    assert 'v-model:value="model.cover" :limit="1"' in drawer
    assert 'v-model:value="model.gallery" :limit="5" value-type="array"' in drawer
    assert 'v-model:value="model.photos" :limit="5"' in drawer
    assert ':disabled="uploadBusy"' in drawer
    index = gen_view_index("inventory", model, ["cover", "gallery", "photos"])
    assert "<ImagePreview value={row.gallery}" in index
    assert "B_SYSTEM_UPLOAD_CREATE" in gen_init_data("inventory", [model])
