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


def test_schema_repository_is_flush_only_and_services_own_transactions() -> None:
    repository_calls = _calls("schema_profile_repository.py")
    assert "flush" in repository_calls
    assert repository_calls.isdisjoint({"commit", "rollback"})
    for service in ("schema_profile_service.py", "schema_field_service.py"):
        calls = _calls(service)
        assert {"commit", "rollback", "refresh"} <= calls


def test_schema_routers_have_no_sql_or_transactions() -> None:
    for router in ("schema_profile_router.py", "schema_field_router.py"):
        calls = _calls(router)
        assert calls.isdisjoint(
            {"add", "commit", "execute", "flush", "rollback", "scalar"}
        )
        assert not any(
            module == "sqlalchemy" or module.startswith("sqlalchemy.sql")
            for module in _imports(router)
        )


def test_schema_chapter_has_no_forbidden_capability() -> None:
    forbidden_imports = {
        "aioftp",
        "aiohttp",
        "boto3",
        "csv",
        "ftplib",
        "httpx",
        "imaplib",
        "openpyxl",
        "pandas",
        "paramiko",
        "requests",
        "xml",
    }
    for path in ROOT.glob("schema_*.py"):
        assert _imports(path.name).isdisjoint(forbidden_imports), path.name
    route_text = "\n".join(
        path.read_text(encoding="utf-8") for path in ROOT.glob("schema_*_router.py")
    )
    for endpoint in (
        "discover",
        "download",
        "import",
        "infer",
        "mapping",
        "parse",
        "preview",
        "snapshot",
        "upload",
    ):
        assert f'"/{endpoint}' not in route_text


def test_schema_openapi_surface_and_serbian_descriptions() -> None:
    specification = app.openapi()
    paths = {
        path: item
        for path, item in specification["paths"].items()
        if "/schema-profiles" in path
    }
    assert len(paths) == 7
    operations = [
        operation
        for item in paths.values()
        for method, operation in item.items()
        if method in {"delete", "get", "patch", "post"}
    ]
    assert len(operations) == 13
    assert {tag for op in operations for tag in op["tags"]} == {
        "supplier-schema-profiles"
    }
    assert all(op.get("description") for op in operations)


def test_schema_files_respect_foundation_line_limit() -> None:
    for path in ROOT.glob("schema_*.py"):
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 350, path.name
