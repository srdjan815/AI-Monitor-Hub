from __future__ import annotations

import ast
from pathlib import Path

MODULE_ROOT = (
    Path(__file__).resolve().parents[1] / "app" / "modules" / "product_content"
)


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(tree: ast.AST) -> set[str]:
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    return imports


def session_calls(tree: ast.AST, names: set[str]) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in names
        and isinstance(node.func.value, ast.Attribute | ast.Name)
    ]


def test_product_content_has_no_duplicate_product_model() -> None:
    classes = [
        node.name
        for node in parsed(MODULE_ROOT / "models.py").body
        if isinstance(node, ast.ClassDef)
    ]
    assert "Product" not in classes


def test_product_content_has_no_downstream_module_dependencies() -> None:
    forbidden = ("supplier", "pricing", "inventory", "import_engine")
    for path in MODULE_ROOT.rglob("*.py"):
        imports = imported_modules(parsed(path))
        assert not any(
            boundary in imported.lower()
            for imported in imports
            for boundary in forbidden
        ), path


def test_repositories_never_own_transactions() -> None:
    paths = [MODULE_ROOT / "repository.py", MODULE_ROOT / "repositories.py"]
    for path in paths:
        calls = session_calls(parsed(path), {"commit", "rollback"})
        assert calls == [], path


def test_routers_have_no_sql_or_transaction_ownership() -> None:
    paths = [MODULE_ROOT / "router.py", *(MODULE_ROOT / "routers").glob("*.py")]
    for path in paths:
        tree = parsed(path)
        sql_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"select", "insert", "update", "delete"}
        ]
        transaction_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback", "flush"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "session"
        ]
        assert sql_calls == [], path
        assert transaction_calls == [], path


def test_service_layer_owns_commit_and_rollback() -> None:
    methods = {
        node.func.attr
        for path in MODULE_ROOT.glob("*service*.py")
        for node in ast.walk(parsed(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"commit", "rollback"} <= methods


def test_repositories_have_no_http_or_request_concerns() -> None:
    for name in ("repository.py", "repositories.py"):
        imports = imported_modules(parsed(MODULE_ROOT / name))
        assert not any(
            dependency.startswith(("fastapi", "httpx", "starlette"))
            for dependency in imports
        )


def test_security_is_centralized_and_module_has_no_execution_engines() -> None:
    router_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (MODULE_ROOT / "routers").glob("*.py")
    )
    assert "bleach" not in router_sources
    assert "sanitize_preview" not in router_sources
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in MODULE_ROOT.rglob("*.py")
    ).lower()
    assert "subprocess" not in source
    assert "media processing" not in source
    assert "publish(" not in source
    assert "openai" not in source
