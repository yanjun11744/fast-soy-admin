"""Tortoise 迁移扫描兼容：忽略 macOS AppleDouble 文件。"""

from functools import wraps

from tortoise.migrations.autodetector import MigrationAutodetector


def install_migration_file_filter() -> None:
    """上游备用扫描支持 AppleDouble 过滤后，可删除此兼容层及配置入口。"""
    original = MigrationAutodetector._disk_migration_names
    if getattr(original, "_ignores_appledouble", False):
        return

    @wraps(original)
    def filtered_names(self: MigrationAutodetector, app_label: str) -> list[str]:
        return [name for name in original(self, app_label) if not name.startswith("._")]

    setattr(filtered_names, "_ignores_appledouble", True)
    MigrationAutodetector._disk_migration_names = filtered_names
