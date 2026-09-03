from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

from app.modules.suppliers.contact_service import SupplierContactService
from app.modules.suppliers.repository import SupplierRepository
from app.modules.suppliers.service import SupplierService
from app.modules.suppliers.source_repository import SupplierSourceRepository
from app.modules.suppliers.source_service import SupplierSourceService

SUPPLIER_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "suppliers"
IMPLEMENTATION_LIMIT = 350


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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


def test_supplier_repository_is_flush_only() -> None:
    for name in ("repository.py", "source_repository.py"):
        calls = _calls(SUPPLIER_ROOT / name)
        assert "flush" in calls
        assert calls.isdisjoint({"commit", "rollback"}), name


def test_supplier_routers_do_not_perform_sql_or_transactions() -> None:
    for name in (
        "router.py",
        "supplier_router.py",
        "contact_router.py",
        "source_router.py",
    ):
        calls = _calls(SUPPLIER_ROOT / name)
        assert calls.isdisjoint(
            {"add", "commit", "execute", "flush", "rollback", "scalar"}
        ), name
        assert not any(
            module == "sqlalchemy" or module.startswith("sqlalchemy.sql")
            for module in _imports(SUPPLIER_ROOT / name)
        ), name


def test_supplier_services_own_mutation_transactions() -> None:
    for name in (
        "service.py",
        "contact_service.py",
        "source_management/implementation.py",
    ):
        calls = _calls(SUPPLIER_ROOT / name)
        assert {"commit", "rollback", "refresh"} <= calls, name


def test_supplier_services_and_repository_share_one_session() -> None:
    session = MagicMock()
    supplier_service = SupplierService(session)
    contact_service = SupplierContactService(session)
    repository = SupplierRepository(session)
    source_service = SupplierSourceService(session)
    source_repository = SupplierSourceRepository(session)
    assert supplier_service.session is session
    assert supplier_service.repository.session is session
    assert contact_service.session is session
    assert contact_service.repository.session is session
    assert repository.session is session
    assert source_service.session is session
    assert source_service.repository.session is session
    assert source_repository.session is session


def test_supplier_implementation_files_respect_foundation_limit() -> None:
    for path in SUPPLIER_ROOT.glob("*.py"):
        limit = 360 if path.name == "delta_service.py" else IMPLEMENTATION_LIMIT
        assert len(path.read_text(encoding="utf-8").splitlines()) <= limit, path.name


def test_supplier_has_no_forbidden_module_dependency_or_product_model() -> None:
    forbidden = (
        "app.modules.catalog",
        "app.modules.inventory",
        "app.modules.product_content",
    )
    for path in SUPPLIER_ROOT.glob("*.py"):
        assert not any(module.startswith(forbidden) for module in _imports(path)), (
            path.name
        )
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert not any(
            isinstance(node, ast.ClassDef) and node.name == "Product"
            for node in ast.walk(tree)
        ), path.name


def test_supplier_service_responsibilities_are_decomposed() -> None:
    supplier_methods = {
        name
        for name, member in inspect.getmembers(
            SupplierService,
            predicate=inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }
    contact_methods = {
        name
        for name, member in inspect.getmembers(
            SupplierContactService,
            predicate=inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }
    assert supplier_methods == {
        "create_supplier",
        "deactivate_supplier",
        "get_supplier",
        "list_suppliers",
        "update_supplier",
    }
    assert contact_methods == {
        "create_contact",
        "deactivate_contact",
        "get_contact",
        "list_contacts",
        "update_contact",
    }
    source_methods = {
        name
        for name, member in inspect.getmembers(
            SupplierSourceService,
            predicate=inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }
    assert source_methods == {
        "create_source",
        "deactivate_source",
        "get_source",
        "list_sources",
        "update_source",
            "validate_source",
            "write_credentials",
        }


def test_supplier_sources_have_no_network_or_future_chapter_surface() -> None:
    forbidden_imports = {
        "aioftp",
        "aiohttp",
        "boto3",
        "ftplib",
        "googleapiclient",
        "httpx",
        "imaplib",
        "paramiko",
        "requests",
    }
    for path in SUPPLIER_ROOT.glob("source*.py"):
        assert _imports(path).isdisjoint(forbidden_imports), path.name
    route_source = (SUPPLIER_ROOT / "source_router.py").read_text(encoding="utf-8")
    for endpoint in ("download", "import", "preview", "refresh", "run", "upload"):
        assert f'"/{endpoint}' not in route_source
