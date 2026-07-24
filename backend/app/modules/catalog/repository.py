from __future__ import annotations

from app.modules.catalog.category_repository import CategoryRepository
from app.modules.catalog.legacy_attribute_repository import (
    LegacyAttributeRepository,
)
from app.modules.catalog.product_repository import ProductRepository


class CatalogRepository(
    CategoryRepository,
    LegacyAttributeRepository,
    ProductRepository,
):
    """Backward-compatible façade over cohesive Catalog repositories."""


__all__ = ["CatalogRepository"]
