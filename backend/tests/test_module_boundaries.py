from __future__ import annotations

import ast
import importlib
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import configure_mappers

from app.api.router import api_router
from app.modules.inventory.router import router as inventory_router


API_ROOT = "http://localhost:8000/api/v1"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = BACKEND_ROOT / "app" / "modules" / "catalog"
INVENTORY_IMPORT = "app.modules.inventory"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_ROOT, timeout=10.0) as client:
        yield client


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_catalog_does_not_import_inventory() -> None:
    violations = {
        str(path.relative_to(BACKEND_ROOT)): sorted(
            module
            for module in imported_modules(path)
            if module == INVENTORY_IMPORT
            or module.startswith(f"{INVENTORY_IMPORT}.")
        )
        for path in CATALOG_ROOT.rglob("*.py")
    }
    assert not {path: imports for path, imports in violations.items() if imports}


def test_no_module_package_name_collisions() -> None:
    collisions = []
    modules_root = BACKEND_ROOT / "app" / "modules"
    for path in modules_root.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        package = path.with_suffix("")
        if package.is_dir() and (package / "__init__.py").exists():
            collisions.append(str(path.relative_to(BACKEND_ROOT)))
    assert collisions == []


def test_router_and_mappers_load_with_optional_inventory() -> None:
    assert any(
        getattr(route, "original_router", None) is inventory_router
        for route in api_router.routes
    )
    paths = {
        route.path
        for route in inventory_router.routes
        if hasattr(route, "path")
    }
    assert "/inventory" in paths
    assert "/inventory/movements" in paths
    assert "/inventory/reservations" in paths
    configure_mappers()


def test_active_modules_import_without_obsolete_paths() -> None:
    module_names = (
        "app.api.router",
        "app.modules.catalog.models",
        "app.modules.catalog.repository",
        "app.modules.catalog.router",
        "app.modules.catalog.schemas",
        "app.modules.catalog.service",
        "app.modules.execution.models",
        "app.modules.execution.repository",
        "app.modules.execution.router",
        "app.modules.inventory.models",
        "app.modules.inventory.repository",
        "app.modules.inventory.router",
    )
    for module_name in module_names:
        importlib.import_module(module_name)

    forbidden = (".venv-1", "backend_product_core_v1")
    source_files = (BACKEND_ROOT / "app").rglob("*.py")
    references = {
        str(path.relative_to(BACKEND_ROOT)): token
        for path in source_files
        for token in forbidden
        if token in path.read_text(encoding="utf-8")
    }
    assert references == {}


def test_transaction_ownership_stays_out_of_repositories_and_routers() -> None:
    modules_root = BACKEND_ROOT / "app" / "modules"
    targets = [
        *modules_root.rglob("repository.py"),
        *modules_root.rglob("router.py"),
        *modules_root.rglob("routers/*.py"),
    ]
    violations = {}
    for path in targets:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        calls_commit = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            for node in ast.walk(tree)
        )
        if calls_commit:
            violations[str(path.relative_to(BACKEND_ROOT))] = "commit"
    assert violations == {}


def test_catalog_product_is_independent_of_inventory(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    category_id: str | None = None
    product_id: str | None = None
    try:
        category = api_client.post(
            "/categories",
            json={
                "name": f"Boundary Category {suffix}",
                "code": f"boundary_category_{suffix}",
            },
        )
        assert category.status_code == 201
        category_id = category.json()["id"]

        product = api_client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Boundary Product {suffix}",
                "code": f"boundary_product_{suffix}",
                "sku": f"BOUNDARY-{suffix}",
            },
        )
        assert product.status_code == 201
        product_id = product.json()["id"]

        balances = api_client.get(
            "/inventory",
            params={
                "product_id": product_id,
                "active_only": "false",
            },
        )
        assert balances.status_code == 200
        assert balances.json() == {"items": [], "total": 0}

        updated = api_client.patch(
            f"/products/{product_id}",
            json={"name": f"Updated Boundary Product {suffix}"},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == (
            f"Updated Boundary Product {suffix}"
        )

        assert api_client.delete(f"/products/{product_id}").status_code == 204
        product_id = None
    finally:
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")
