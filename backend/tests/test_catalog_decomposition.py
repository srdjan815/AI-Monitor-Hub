from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

from app.modules.catalog.category_repository import CategoryRepository
from app.modules.catalog.category_service import CategoryService
from app.modules.catalog.legacy_attribute_repository import (
    LegacyAttributeRepository,
)
from app.modules.catalog.legacy_attribute_service import LegacyAttributeService
from app.modules.catalog.product_repository import ProductRepository
from app.modules.catalog.product_service import ProductService
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.service import CatalogService


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "catalog"
PUBLIC_METHODS = {
    "create_attribute",
    "create_attribute_type",
    "create_category",
    "create_product",
    "deactivate_attribute_type",
    "deactivate_category",
    "deactivate_product",
    "get_attribute_type",
    "get_category_tree",
    "list_attribute_types",
    "reorder_category_attributes",
    "update_attribute",
    "update_attribute_type",
    "update_category",
    "update_product",
}


def _public_coroutines(model: type[object]) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(
            model,
            predicate=inspect.iscoroutinefunction,
        )
        if not name.startswith("_")
    }


def test_catalog_service_facade_preserves_public_surface() -> None:
    assert _public_coroutines(CatalogService) == PUBLIC_METHODS
    assert {
        "create_category",
        "update_category",
        "deactivate_category",
        "get_category_tree",
    } == _public_coroutines(CategoryService)
    assert {
        "create_product",
        "update_product",
        "deactivate_product",
    } == _public_coroutines(ProductService)
    assert {
        "create_attribute",
        "update_attribute",
        "reorder_category_attributes",
        "list_attribute_types",
        "get_attribute_type",
        "create_attribute_type",
        "update_attribute_type",
        "deactivate_attribute_type",
    } == _public_coroutines(LegacyAttributeService)


def test_catalog_facades_share_one_session_context() -> None:
    session = MagicMock()
    service = CatalogService(session)
    repository = CatalogRepository(session)
    assert service.session is session
    assert service.repository.session is session
    assert repository.session is session


def test_catalog_repository_responsibilities_are_disjoint() -> None:
    assert hasattr(CategoryRepository, "create_category")
    assert not hasattr(CategoryRepository, "create_product")
    assert hasattr(ProductRepository, "create_product")
    assert not hasattr(ProductRepository, "create_attribute")
    assert hasattr(LegacyAttributeRepository, "create_attribute")
    assert not hasattr(LegacyAttributeRepository, "create_product")


def test_catalog_repositories_remain_flush_only() -> None:
    for name in (
        "category_repository.py",
        "legacy_attribute_repository.py",
        "product_repository.py",
    ):
        path = CATALOG_ROOT / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        ]
        assert forbidden == [], name
