from __future__ import annotations

import uuid
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.attribute_models import (
    AttributeChangeEvent,
    ProductAttributeValue,
)
from app.modules.catalog.models import (
    AttributeDefinition,
)
from app.modules.catalog.platform_models import (
    AttributeDependency,
    AttributeFamily,
    AttributeFormula,
    AttributePromptVersion,
    AttributeTemplate,
)

ModelT = TypeVar("ModelT")


class ProductAttributeRepositorySupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, model: type[ModelT], entity_id: uuid.UUID) -> ModelT | None:
        return await self.session.get(model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def mutate(self, entity: ModelT, changes: dict[str, Any]) -> ModelT:
        for field, value in changes.items():
            setattr(entity, field, value)
        await self.session.flush()
        return entity

    async def count(self, model: type[Any], *criteria: Any) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(model).where(*criteria)
            )
            or 0
        )

    async def dashboard(self) -> dict[str, int | None]:
        return {
            "total_definitions": await self.count(AttributeDefinition),
            "global_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.scope == "GLOBAL"
            ),
            "category_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.scope == "CATEGORY"
            ),
            "filter_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.is_filterable.is_(True)
            ),
            "compatibility_definitions": await self.count(
                AttributeDefinition,
                AttributeDefinition.is_compatibility_attribute.is_(True),
            ),
            "ai_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.use_ai.is_(True)
            ),
            "active_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.is_active.is_(True)
            ),
            "inactive_definitions": await self.count(
                AttributeDefinition, AttributeDefinition.is_active.is_(False)
            ),
            "pending_review_values": await self.count(
                ProductAttributeValue,
                ProductAttributeValue.approval_status == "PENDING_REVIEW",
                ProductAttributeValue.is_active.is_(True),
            ),
            "invalid_values": await self.count(
                ProductAttributeValue,
                ProductAttributeValue.validation_status == "INVALID",
                ProductAttributeValue.is_active.is_(True),
            ),
            "warning_values": await self.count(
                ProductAttributeValue,
                ProductAttributeValue.validation_status == "WARNING",
                ProductAttributeValue.is_active.is_(True),
            ),
            "low_confidence_values": await self.count(
                ProductAttributeValue,
                ProductAttributeValue.confidence_score < 0.8,
                ProductAttributeValue.is_active.is_(True),
            ),
            "recent_changes": await self.count(AttributeChangeEvent),
            "products_with_missing_required_attributes": None,
            "families": await self.count(AttributeFamily),
            "templates": await self.count(AttributeTemplate),
            "dependencies": await self.count(
                AttributeDependency, AttributeDependency.is_active.is_(True)
            ),
            "formula_attributes": await self.count(
                AttributeFormula,
                AttributeFormula.formula_kind == "FORMULA",
                AttributeFormula.is_active.is_(True),
            ),
            "derived_attributes": await self.count(
                AttributeFormula,
                AttributeFormula.formula_kind == "DERIVED",
                AttributeFormula.is_active.is_(True),
            ),
            "prompt_versions": await self.count(AttributePromptVersion),
            "locked_values": await self.count(
                ProductAttributeValue,
                ProductAttributeValue.is_locked.is_(True),
                ProductAttributeValue.is_active.is_(True),
            ),
        }


__all__ = ["ProductAttributeRepositorySupport"]
