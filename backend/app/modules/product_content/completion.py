from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.core.config import settings
from app.modules.product_content.constants import (
    ConditionOperator,
    MAX_CONDITIONS_PER_ITEM,
    PreviewMode,
)
from app.modules.product_content.models import (
    ContentTemplate,
    ContentTemplateCondition,
    ContentTemplateItem,
)
from app.modules.product_content.repositories import ContentRepository
from app.modules.product_content.schemas import PreviewRequest
from app.modules.product_content.security import (
    compare_values,
    interpolate_variables,
    sanitize_preview,
)


class ContentCompletionService:
    """Safe variable and template rendering orchestration.

    Storage queries are delegated to ContentRepository. This service performs
    no dynamic imports, attribute traversal, eval, exec, or callable execution.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.repository = ContentRepository(session)

    async def _required(
        self,
        model: type[Any],
        entity_id: uuid.UUID,
        label: str,
    ) -> Any:
        entity = await self.repository.get(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        return entity

    async def variables(self, product_id: uuid.UUID) -> dict[str, Any]:
        product = await self._required(Product, product_id, "Product")
        values = {
            "ProductName": product.name,
            "Manufacturer": product.manufacturer or "",
            "Brand": product.brand or "",
            "SKU": product.sku or "",
            "EAN": product.ean or "",
            "MPN": product.mpn or "",
        }
        for value, api_name in await self.repository.product_attribute_variables(
            product_id
        ):
            if api_name and not api_name.startswith("_"):
                values[api_name] = value.display_value
        return values

    async def render(
        self,
        product_id: uuid.UUID,
        template_id: uuid.UUID,
        data: PreviewRequest,
    ) -> dict[str, Any]:
        if data.trusted_raw and not settings.product_content_trusted_raw_preview:
            raise HTTPException(
                status_code=403,
                detail="Trusted raw preview is disabled",
            )
        await self._required(ContentTemplate, template_id, "Template")
        values = await self.variables(product_id)
        rows = await self.repository.template_render_rows(template_id, data.language_id)
        conditions = await self.repository.template_conditions(
            [item.id for item, _revision in rows]
        )
        grouped: dict[uuid.UUID, list[ContentTemplateCondition]] = {}
        for condition in conditions:
            grouped.setdefault(condition.template_item_id, []).append(condition)

        blocks: list[dict[str, Any]] = []
        unknown: set[str] = set()
        malformed: set[str] = set()
        for item, revision in rows:
            item_conditions = grouped.get(item.id, [])
            visible = (
                self._conditions(item_conditions, values)
                if item_conditions
                else self._legacy_condition(item, values)
            )
            if not visible:
                continue
            interpolated, missing, invalid = interpolate_variables(
                revision.content,
                values,
                trusted_raw=data.trusted_raw,
            )
            unknown.update(missing)
            malformed.update(invalid)
            rendered = (
                interpolated
                if data.viewport == PreviewMode.RAW and data.trusted_raw
                else sanitize_preview(interpolated)
            )
            blocks.append(
                {
                    "id": item.library_item_id,
                    "html": rendered,
                    "raw": revision.content,
                }
            )
        return {
            "viewport": data.viewport,
            "status": data.status,
            "blocks": blocks,
            "unknown_variables": sorted(unknown),
            "malformed_variables": sorted(malformed),
            "trusted_raw": data.trusted_raw,
            "rendered_html": "\n".join(block["html"] for block in blocks),
        }

    @staticmethod
    def _legacy_condition(
        item: ContentTemplateItem,
        values: dict[str, Any],
    ) -> bool:
        if not item.condition_source:
            return True
        result = compare_values(
            item.condition_comparator or "EXISTS",
            values.get(item.condition_source),
            item.condition_value,
        )
        return (
            not result if item.condition_operator == ConditionOperator.NOT else result
        )

    @staticmethod
    def _conditions(
        conditions: list[ContentTemplateCondition],
        values: dict[str, Any],
    ) -> bool:
        if not conditions or len(conditions) > MAX_CONDITIONS_PER_ITEM:
            return False
        result: bool | None = None
        for condition in conditions:
            current = compare_values(
                condition.comparator,
                values.get(condition.source),
                condition.expected_value,
            )
            if condition.boolean_operator == ConditionOperator.NOT:
                current = not current
            if result is None:
                result = current
            elif condition.boolean_operator == ConditionOperator.OR:
                result = result or current
            else:
                result = result and current
        return bool(result)
