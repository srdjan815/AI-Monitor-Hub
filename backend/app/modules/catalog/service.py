from __future__ import annotations

from app.modules.catalog.category_service import CategoryService
from app.modules.catalog.legacy_attribute_service import (
    LegacyAttributeService,
)
from app.modules.catalog.product_service import ProductService


class CatalogService(
    CategoryService,
    LegacyAttributeService,
    ProductService,
):
    """Backward-compatible façade over cohesive Catalog services."""


__all__ = ["CatalogService"]
