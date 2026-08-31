from __future__ import annotations

import ast
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "suppliers"


def _calls(name: str) -> set[str]:
    tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def _imports(name: str) -> set[str]:
    tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
    return {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


def test_mapping_repository_is_flush_only_and_services_own_transactions() -> None:
    calls = _calls("mapping_profile_repository.py")
    assert "flush" in calls
    assert calls.isdisjoint({"commit", "rollback"})
    for service in ("mapping_profile_service.py", "mapping_rule_service.py"):
        assert {"commit", "rollback", "refresh"} <= _calls(service)


def test_mapping_routers_have_no_sql_or_transactions() -> None:
    for router in ("mapping_profile_router.py", "mapping_rule_router.py"):
        assert _calls(router).isdisjoint(
            {"add", "commit", "execute", "flush", "rollback", "scalar"}
        )
        assert not any(
            module == "sqlalchemy" or module.startswith("sqlalchemy.sql")
            for module in _imports(router)
        )


def test_mapping_has_no_execution_catalog_or_future_capability() -> None:
    forbidden = {
        "aiohttp",
        "app.modules.catalog",
        "app.modules.execution",
        "app.modules.inventory",
        "csv",
        "ftplib",
        "httpx",
        "openpyxl",
        "pandas",
        "requests",
        "xml",
    }
    for path in ROOT.glob("mapping_*.py"):
        assert not any(
            module in forbidden or module.startswith("app.modules.catalog")
            for module in _imports(path.name)
        ), path.name
    route_text = "\n".join(
        path.read_text(encoding="utf-8") for path in ROOT.glob("mapping_*_router.py")
    )
    for endpoint in (
        "execute",
        "import",
        "preview",
        "run",
        "snapshot",
        "transform",
    ):
        assert f'"/{endpoint}' not in route_text


def test_mapping_openapi_surface_and_serbian_descriptions() -> None:
    specification = app.openapi()
    paths = {
        path: item
        for path, item in specification["paths"].items()
        if "/mapping-profiles" in path
    }
    assert len(paths) == 8
    operations = [
        operation
        for item in paths.values()
        for method, operation in item.items()
        if method in {"delete", "get", "patch", "post"}
    ]
    assert len(operations) == 14
    assert {tag for op in operations for tag in op["tags"]} == {
        "supplier-mapping-profiles"
    }
    assert all(op.get("description") for op in operations)


def test_mapping_files_respect_foundation_line_limit() -> None:
    for path in ROOT.glob("mapping_*.py"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 350, path.name
