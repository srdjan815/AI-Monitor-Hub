from __future__ import annotations

import ast
from pathlib import Path

from app.core.security import ROLE_PERMISSIONS
from app.main import app
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
    SupplierSnapshotItem,
)

ROOT = Path(__file__).parents[1]
SUPPLIERS = ROOT / "app" / "modules" / "suppliers"
MIGRATION = ROOT / "alembic" / "versions" / "a4b5c6d7e8f9_supplier_snapshot_engine.py"


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_snapshot_layers_preserve_transaction_ownership() -> None:
    repository_calls = _calls(SUPPLIERS / "snapshot_repository.py")
    assert "commit" not in repository_calls
    assert "rollback" not in repository_calls
    for router in SUPPLIERS.glob("snapshot_*_router.py"):
        text = router.read_text(encoding="utf-8")
        assert "select(" not in text
        assert "session.execute" not in text
    storage = (SUPPLIERS / "snapshot_archive_storage.py").read_text(encoding="utf-8")
    serializer = (SUPPLIERS / "snapshot_archive_format.py").read_text(encoding="utf-8")
    assert "AsyncSession" not in storage
    assert "AsyncSession" not in serializer
    assert ".commit(" not in storage
    assert ".rollback(" not in serializer


def test_snapshot_migration_extends_frozen_acquisition_head() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "a3b4c5d6e7f8"' in text
    assert text.count("def upgrade(") == 1
    assert text.count("def downgrade(") == 1
    assert {
        SupplierSnapshot.__tablename__,
        SupplierSnapshotItem.__tablename__,
        SupplierSnapshotArchiveOperation.__tablename__,
    } == {
        "supplier_snapshots",
        "supplier_snapshot_items",
        "supplier_snapshot_archive_operations",
    }


def test_snapshot_openapi_has_no_generic_update_or_delete() -> None:
    paths = {
        path: operations
        for path, operations in app.openapi()["paths"].items()
        if "/snapshots" in path
    }
    assert len(paths) == 13
    assert all(
        "delete" not in operations and "patch" not in operations
        for operations in paths.values()
    )
    assert all(
        operation.get("summary") and operation.get("description")
        for operations in paths.values()
        for operation in operations.values()
    )


def test_snapshot_permissions_separate_export_and_offload() -> None:
    required = {
        "snapshots.read",
        "snapshots.create",
        "snapshots.verify",
        "snapshots.archive",
        "snapshots.offload",
        "snapshots.restore",
    }
    assert required.issubset(ROLE_PERMISSIONS["supplier_admin"])
    assert "snapshots.archive" in ROLE_PERMISSIONS["snapshot_operator"]
    assert "snapshots.offload" not in ROLE_PERMISSIONS["snapshot_operator"]
    assert ROLE_PERMISSIONS["read_only"].intersection(required) == {"snapshots.read"}
