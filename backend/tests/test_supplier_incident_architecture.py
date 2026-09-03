from __future__ import annotations

import ast
from pathlib import Path

from app.core.security import ROLE_PERMISSIONS
from app.main import app
from app.modules.suppliers.incident_models import (
    SupplierIncident, SupplierIncidentComment, SupplierIncidentEvent,
    SupplierIncidentLink, SupplierIncidentRule,
)

ROOT = Path(__file__).parents[1]
SUPPLIERS = ROOT / "app" / "modules" / "suppliers"
MIGRATION = ROOT / "alembic" / "versions" / "a6b7c8d9e0f1_supplier_incident_center.py"


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


def test_incident_layers_and_frozen_boundaries() -> None:
    calls = _calls(SUPPLIERS / "incident_repository.py")
    assert "commit" not in calls and "rollback" not in calls
    router = (SUPPLIERS / "incident_router.py").read_text(encoding="utf-8")
    assert "select(" not in router and "session.execute" not in router
    helpers = (SUPPLIERS / "incident_safety.py").read_text(encoding="utf-8") + (SUPPLIERS / "incident_rules.py").read_text(encoding="utf-8")
    assert "AsyncSession" not in helpers and "eval(" not in helpers and "exec(" not in helpers
    service = (SUPPLIERS / "incident_service.py").read_text(encoding="utf-8")
    assert "Catalog" not in service and "Inventory" not in service


def test_incident_migration_is_additive() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "a5b6c7d8e9f1"' in text
    assert text.count("def upgrade(") == 1 and text.count("def downgrade(") == 1
    assert {SupplierIncident.__tablename__, SupplierIncidentEvent.__tablename__, SupplierIncidentComment.__tablename__, SupplierIncidentLink.__tablename__, SupplierIncidentRule.__tablename__} == {
        "supplier_incidents", "supplier_incident_events", "supplier_incident_comments", "supplier_incident_links", "supplier_incident_rules",
    }


def test_incident_openapi_and_permissions() -> None:
    paths = {path: operations for path, operations in app.openapi()["paths"].items() if "supplier-incident" in path}
    assert len(paths) >= 25
    assert all(operation.get("summary") and operation.get("description") for operations in paths.values() for operation in operations.values())
    required = {
        "incidents.read", "incidents.create", "incidents.acknowledge",
        "incidents.assign", "incidents.manage", "incidents.resolve",
        "incidents.dismiss", "incidents.suppress", "incidents.comment",
        "incident_rules.read", "incident_rules.manage",
    }
    assert required <= ROLE_PERMISSIONS["supplier_admin"]
    assert ROLE_PERMISSIONS["read_only"].intersection(required) == {"incidents.read", "incident_rules.read"}
