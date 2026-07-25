from __future__ import annotations

import ast
from pathlib import Path

from app.core.security import ROLE_PERMISSIONS
from app.main import app
from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange, SupplierDeltaItem, SupplierDeltaRun,
)

ROOT = Path(__file__).parents[1]
SUPPLIERS = ROOT / "app" / "modules" / "suppliers"
MIGRATION = ROOT / "alembic" / "versions" / "a5b6c7d8e9f1_supplier_delta_engine.py"


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_delta_layering_and_frozen_boundaries() -> None:
    calls = _calls(SUPPLIERS / "delta_repository.py")
    assert "commit" not in calls and "rollback" not in calls
    router = (SUPPLIERS / "delta_router.py").read_text(encoding="utf-8")
    assert "select(" not in router and "session.execute" not in router
    helpers = (SUPPLIERS / "delta_comparison.py").read_text(encoding="utf-8")
    assert "AsyncSession" not in helpers and "Catalog" not in helpers
    service = (SUPPLIERS / "delta_service.py").read_text(encoding="utf-8")
    assert "Catalog" not in service and "Inventory" not in service


def test_delta_migration_and_models_are_additive() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "a4b5c6d7e8f9"' in text
    assert text.count("def upgrade(") == 1 and text.count("def downgrade(") == 1
    assert {SupplierDeltaRun.__tablename__, SupplierDeltaItem.__tablename__, SupplierDeltaFieldChange.__tablename__} == {
        "supplier_delta_runs", "supplier_delta_items", "supplier_delta_field_changes",
    }


def test_delta_openapi_and_permissions() -> None:
    paths = {path: ops for path, ops in app.openapi()["paths"].items() if "/deltas" in path}
    assert len(paths) == 10
    assert all(op.get("summary") and op.get("description") for ops in paths.values() for op in ops.values())
    required = {"deltas.read", "deltas.calculate", "deltas.cancel"}
    assert required <= ROLE_PERMISSIONS["supplier_admin"]
    assert ROLE_PERMISSIONS["read_only"].intersection(required) == {"deltas.read"}
