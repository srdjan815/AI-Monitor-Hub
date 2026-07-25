from __future__ import annotations

import ast
from pathlib import Path

from app.main import app
from app.modules.suppliers.acquisition_models import (
    SupplierAcquisitionIssue,
    SupplierAcquisitionRun,
    SupplierStagedRecord,
)

ROOT = Path(__file__).parents[1]
SUPPLIERS = ROOT / "app" / "modules" / "suppliers"
MIGRATION = (
    ROOT / "alembic" / "versions" / "a3b4c5d6e7f8_supplier_acquisition_engine.py"
)


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_acquisition_layers_own_only_their_responsibilities() -> None:
    repository_calls = _calls(SUPPLIERS / "acquisition_repository.py")
    assert "commit" not in repository_calls
    assert "rollback" not in repository_calls
    for router in (
        SUPPLIERS / "acquisition_execution_router.py",
        SUPPLIERS / "acquisition_query_router.py",
    ):
        text = router.read_text(encoding="utf-8")
        assert "select(" not in text
        assert "session.execute" not in text
    for parser_or_adapter in (
        SUPPLIERS / "acquisition_parsers.py",
        SUPPLIERS / "acquisition_adapters.py",
    ):
        text = parser_or_adapter.read_text(encoding="utf-8")
        assert "AsyncSession" not in text
        assert ".commit(" not in text
        assert ".rollback(" not in text
    transformation = (SUPPLIERS / "acquisition_transformations.py").read_text(
        encoding="utf-8"
    )
    assert "eval(" not in transformation
    assert "exec(" not in transformation


def test_migration_extends_frozen_head_and_models_are_registered() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "a2b3c4d5e6f7"' in text
    assert text.count("def upgrade(") == 1
    assert text.count("def downgrade(") == 1
    table_names = {
        SupplierAcquisitionRun.__tablename__,
        SupplierStagedRecord.__tablename__,
        SupplierAcquisitionIssue.__tablename__,
    }
    assert table_names == {
        "supplier_acquisition_runs",
        "supplier_staged_acquisition_records",
        "supplier_acquisition_issues",
    }


def test_acquisition_openapi_is_bounded_and_serbian_documented() -> None:
    schema = app.openapi()
    paths = {
        path: operations
        for path, operations in schema["paths"].items()
        if "/acquisitions" in path
    }
    assert len(paths) == 10
    assert all(
        operation.get("summary") and operation.get("description")
        for operations in paths.values()
        for operation in operations.values()
    )
    list_operation = paths[
        "/api/v1/suppliers/{supplier_id}/sources/{source_id}/acquisitions"
    ]["get"]
    limit = next(
        parameter
        for parameter in list_operation["parameters"]
        if parameter["name"] == "limit"
    )
    assert limit["schema"]["maximum"] == 500


def test_acquisition_permissions_are_registered() -> None:
    from app.core.security import ROLE_PERMISSIONS

    assert {
        "acquisitions.read",
        "acquisitions.execute",
        "acquisitions.upload",
        "acquisitions.cancel",
    }.issubset(ROLE_PERMISSIONS["supplier_admin"])
