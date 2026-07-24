from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from app.modules.catalog.attribute_definition_repository import (
    AttributeDefinitionRepository,
)
from app.modules.catalog.attribute_definition_service import (
    AttributeDefinitionService,
)
from app.modules.catalog.attribute_option_repository import (
    AttributeOptionRepository,
)
from app.modules.catalog.attribute_option_service import AttributeOptionService
from app.modules.catalog.attribute_platform_repository import (
    AttributePlatformRepository,
)
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.category_attribute_repository import (
    CategoryAttributeRepository,
)
from app.modules.catalog.category_attribute_service import (
    CategoryAttributeService,
)
from app.modules.catalog.product_attribute_value_repository import (
    ProductAttributeValueRepository,
)
from app.modules.catalog.product_attribute_value_service import (
    ProductAttributeValueService,
)

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "app" / "modules" / "catalog"
SPLIT_FILES = (
    "attribute_service_support.py",
    "attribute_definition_service.py",
    "category_attribute_service.py",
    "attribute_option_service.py",
    "product_attribute_value_service.py",
    "attribute_repository_support.py",
    "attribute_definition_repository.py",
    "category_attribute_repository.py",
    "attribute_option_repository.py",
    "product_attribute_value_repository.py",
    "attribute_platform_repository.py",
)


def test_product_attribute_facades_preserve_public_surface() -> None:
    service_methods = {
        "create_group",
        "create_definition",
        "create_assignment",
        "create_option",
        "create_rule",
        "resolved_page",
        "validate_value",
        "write_value",
        "bulk_write",
        "change_approval",
        "deactivate_value",
    }
    repository_methods = {
        "list_groups",
        "list_definitions",
        "resolved_definitions_page",
        "list_assignments",
        "list_options",
        "values",
        "history",
        "changes",
        "list_formulas",
    }
    assert all(hasattr(ProductAttributeService, name) for name in service_methods)
    assert all(hasattr(ProductAttributeRepository, name) for name in repository_methods)


def test_product_attribute_facades_share_one_session() -> None:
    session = MagicMock()
    service = ProductAttributeService(session)
    repository = ProductAttributeRepository(session)
    assert service.session is session
    assert service.repository.session is session
    assert repository.session is session


def test_product_attribute_responsibilities_are_disjoint() -> None:
    assert hasattr(AttributeDefinitionService, "create_definition")
    assert not hasattr(AttributeDefinitionService, "write_value")
    assert hasattr(CategoryAttributeService, "create_assignment")
    assert not hasattr(CategoryAttributeService, "create_option")
    assert hasattr(AttributeOptionService, "create_option")
    assert not hasattr(AttributeOptionService, "bulk_write")
    assert hasattr(ProductAttributeValueService, "bulk_write")
    assert not hasattr(ProductAttributeValueService, "create_definition")

    assert hasattr(AttributeDefinitionRepository, "list_definitions")
    assert not hasattr(AttributeDefinitionRepository, "values")
    assert hasattr(CategoryAttributeRepository, "list_assignments")
    assert hasattr(AttributeOptionRepository, "list_options")
    assert hasattr(ProductAttributeValueRepository, "values")
    assert hasattr(AttributePlatformRepository, "list_formulas")


def test_product_attribute_splits_remain_cohesive_and_flush_only() -> None:
    for name in SPLIT_FILES:
        path = CATALOG_ROOT / name
        source = path.read_text(encoding="utf-8")
        assert len(source.splitlines()) <= 350, name
        tree = ast.parse(source, filename=str(path))
        if "repository" not in name:
            continue
        forbidden = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"commit", "rollback"}
        ]
        assert forbidden == [], name
