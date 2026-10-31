from pathlib import Path

import pytest
from tortoise.apps import Apps
from tortoise.connection import ConnectionHandler
from tortoise.migrations.autodetector import MigrationAutodetector
from tortoise.migrations.graph import MigrationKey

from app.core.migration_compat import install_migration_file_filter


@pytest.mark.parametrize("real_migration", [False, True])
def test_appledouble_files_do_not_become_migration_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real_migration: bool) -> None:
    for name in ("__init__.py", ".___init__.py", "._0001_initial.py"):
        (tmp_path / name).write_bytes(b"AppleDouble metadata")
    if real_migration:
        (tmp_path / "0001_initial.py").touch()
    monkeypatch.setattr("tortoise.migrations.autodetector.migrations_module_path", lambda _: tmp_path)
    install_migration_file_filter()
    install_migration_file_filter()
    detector = MigrationAutodetector(Apps({}, ConnectionHandler()), {"example": {"migrations": "migrations.example"}})

    assert detector._leaf_nodes("example") == ([MigrationKey("example", "0001_initial")] if real_migration else [])
