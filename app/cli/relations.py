"""Discover exportable parent/child relationships without importing business models."""

from app.cli.options import BackendFeatureOptions
from app.cli.parser import ModelInfo, RelationInfo


def excel_field_names(model: ModelInfo, options: BackendFeatureOptions) -> list[str]:
    excluded = set(options.exclude_fields.get(model.name, []))
    names = [field.name for field in model.schema_fields if field.name not in excluded]
    names.extend(f"{relation.name}_id" for relation in model.relations if relation.relation_type in {"ForeignKeyField", "OneToOneField"} and f"{relation.name}_id" not in excluded)
    return names


def export_children(module: str, parent: ModelInfo, models: list[ModelInfo], options: BackendFeatureOptions) -> list[tuple[ModelInfo, RelationInfo]]:
    """Only declared same-module FK/one-to-one children with a readable Excel resource."""
    targets = {f"app_system.{parent.name}", f"app_{module}.{parent.name}", f"models.{parent.name}"}
    children = []
    for child in models:
        if child.name == parent.name or not excel_field_names(child, options) or "list" not in options.enable_routes.get(child.name, {"list"}):
            continue
        for relation in child.relations:
            if relation.relation_type in {"ForeignKeyField", "OneToOneField"} and relation.related_model in targets:
                children.append((child, relation))
    return children
