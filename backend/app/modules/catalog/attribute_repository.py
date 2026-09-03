from __future__ import annotations

from app.modules.catalog.attribute_definition_repository import (
    AttributeDefinitionRepository,
)
from app.modules.catalog.attribute_option_repository import (
    AttributeOptionRepository,
)
from app.modules.catalog.attribute_platform_repository import (
    AttributePlatformRepository,
)
from app.modules.catalog.category_attribute_repository import (
    CategoryAttributeRepository,
)
from app.modules.catalog.product_attribute_value_repository import (
    ProductAttributeValueRepository,
)


class ProductAttributeRepository(
    AttributeDefinitionRepository,
    CategoryAttributeRepository,
    AttributeOptionRepository,
    ProductAttributeValueRepository,
    AttributePlatformRepository,
):
    """Backward-compatible façade over cohesive attribute repositories."""


__all__ = ["ProductAttributeRepository"]
