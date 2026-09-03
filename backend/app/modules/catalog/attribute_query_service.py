from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.modules.catalog.attribute_models import ProductAttributeValue
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.enums import AttributeStorageKind
from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
    Product,
)
from app.modules.catalog.platform_models import AttributeTemplate
from app.modules.catalog.schemas.product_attributes import (
    AttributeDefinitionRead,
    CategoryAssignmentRead,
    ResolvedAttribute,
    ResolvedAttributePage,
)


class AttributeQueryService:
    """Bounded read model for inherited and product-resolved attributes."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = ProductAttributeRepository(session)

    async def resolved_page(
        self,
        category_id: uuid.UUID,
        *,
        product: Product | None,
        include_unset: bool,
        scope: str | None,
        group_id: uuid.UUID | None,
        family_id: uuid.UUID | None,
        template_id: uuid.UUID | None,
        limit: int,
        cursor: str | None,
        filter_only: bool = False,
        compatibility_only: bool = False,
    ) -> ResolvedAttributePage:
        chain = await self.repository.list_category_chain(category_id)
        if not chain:
            raise HTTPException(status_code=404, detail="Category not found")
        cursor_filters = {
            "category_id": category_id,
            "product_id": product.id if product else None,
            "include_unset": include_unset,
            "scope": scope,
            "group_id": group_id,
            "family_id": family_id,
            "template_id": template_id,
            "limit": limit,
            "filter_only": filter_only,
            "compatibility_only": compatibility_only,
        }
        after, snapshot_at, snapshot_cursor = await self._cursor_state(
            cursor,
            cursor_filters,
        )
        definitions, total, has_next = await self.repository.resolved_definitions_page(
            category_ids=[category.id for category in chain],
            product_id=product.id if product else None,
            include_unset=include_unset,
            scope=scope,
            group_id=group_id,
            family_id=family_id,
            template_ids=await self._template_chain(template_id),
            filter_only=filter_only,
            compatibility_only=compatibility_only,
            snapshot_at=snapshot_at,
            after=after,
            limit=limit,
        )
        winners = await self._winner_assignments(chain, definitions)
        values_by_attribute = await self._page_values(product, definitions)
        items = [
            await self._resolved_item(
                definition,
                winners.get(definition.id),
                values_by_attribute.get(definition.id, []),
                product,
                chain,
            )
            for definition in definitions
        ]
        next_cursor = None
        if has_next and definitions:
            last = definitions[-1]
            next_cursor = encode_cursor(
                "resolved-attributes",
                cursor_filters,
                [
                    last.created_at.isoformat(),
                    str(last.id),
                    snapshot_at.isoformat(),
                    snapshot_cursor,
                ],
            )
        return ResolvedAttributePage(
            items=items,
            total=total,
            limit=limit,
            next_cursor=next_cursor,
            snapshot_cursor=snapshot_cursor,
            snapshot_at=snapshot_at,
        )

    async def resolved_layout(
        self,
        category_id: uuid.UUID,
        *,
        product: Product | None = None,
    ) -> list[ResolvedAttribute]:
        """Compatibility-only complete materialization built from bounded pages."""
        items: list[ResolvedAttribute] = []
        cursor: str | None = None
        while True:
            page = await self.resolved_page(
                category_id,
                product=product,
                include_unset=True,
                scope=None,
                group_id=None,
                family_id=None,
                template_id=None,
                limit=500,
                cursor=cursor,
            )
            items.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                return items

    async def _winner_assignments(
        self,
        chain: list[Category],
        definitions: list[AttributeDefinition],
    ) -> dict[uuid.UUID, CategoryAttribute]:
        depth = {category.id: index for index, category in enumerate(chain)}
        winners: dict[uuid.UUID, CategoryAttribute] = {}
        assignments = await self.repository.list_page_assignments(
            [category.id for category in chain],
            [definition.id for definition in definitions],
        )
        for assignment in assignments:
            current = winners.get(assignment.attribute_id)
            if (
                current is None
                or depth[assignment.category_id] > depth[current.category_id]
            ):
                winners[assignment.attribute_id] = assignment
        return winners

    async def _cursor_state(
        self,
        cursor: str | None,
        cursor_filters: dict[str, Any],
    ) -> tuple[
        tuple[datetime, uuid.UUID] | None,
        datetime,
        int,
    ]:
        if cursor is None:
            return (
                None,
                datetime.now(UTC),
                await self.repository.latest_cursor(),
            )
        try:
            position = decode_cursor(
                cursor,
                "resolved-attributes",
                cursor_filters,
            )
            if len(position) != 4:
                raise InvalidCursorError("Cursor position is invalid")
            after_created_at = datetime.fromisoformat(str(position[0]))
            snapshot_at = datetime.fromisoformat(str(position[2]))
            if after_created_at.tzinfo is None or snapshot_at.tzinfo is None:
                raise InvalidCursorError("Cursor timestamp is invalid")
            return (
                (after_created_at, uuid.UUID(str(position[1]))),
                snapshot_at,
                int(position[3]),
            )
        except (InvalidCursorError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_CURSOR", "message": str(exc)},
            ) from exc

    async def _template_chain(
        self,
        template_id: uuid.UUID | None,
    ) -> set[uuid.UUID]:
        template_ids: set[uuid.UUID] = set()
        template = (
            await self.repository.get(AttributeTemplate, template_id)
            if template_id
            else None
        )
        while template is not None and template.id not in template_ids:
            template_ids.add(template.id)
            template = (
                await self.repository.get(
                    AttributeTemplate,
                    template.parent_template_id,
                )
                if template.parent_template_id
                else None
            )
        return template_ids

    async def _page_values(
        self,
        product: Product | None,
        definitions: list[AttributeDefinition],
    ) -> dict[uuid.UUID, list[ProductAttributeValue]]:
        values_by_attribute: dict[uuid.UUID, list[ProductAttributeValue]] = {}
        if product is None:
            return values_by_attribute
        values = await self.repository.values_for_attributes(
            product.id,
            [definition.id for definition in definitions],
        )
        for value in values:
            values_by_attribute.setdefault(
                value.attribute_definition_id,
                [],
            ).append(value)
        return values_by_attribute

    async def _resolved_item(
        self,
        definition: AttributeDefinition,
        assignment: CategoryAttribute | None,
        values: list[ProductAttributeValue],
        product: Product | None,
        chain: list[Category],
    ) -> ResolvedAttribute:
        resolved_value: Any | None = None
        display: str | None = None
        read_only = definition.storage_kind in {
            AttributeStorageKind.CORE_FIELD.value,
            AttributeStorageKind.RELATION.value,
            AttributeStorageKind.CATEGORY_PATH.value,
        }
        if read_only and product:
            resolved_value = self._system_value(product, definition, chain)
            display = None if resolved_value is None else str(resolved_value)
        elif values:
            resolved_value = (
                [record.canonical_value for record in values]
                if definition.allows_multiple
                else values[0].canonical_value
            )
            display = (
                ", ".join(record.display_value for record in values)
                if definition.allows_multiple
                else values[0].display_value
            )
        return ResolvedAttribute(
            definition=AttributeDefinitionRead.model_validate(definition),
            assignment=(
                CategoryAssignmentRead.model_validate(assignment)
                if assignment
                else None
            ),
            inherited_from_category_id=(assignment.category_id if assignment else None),
            group_id=(
                assignment.group_id_override
                if assignment and assignment.group_id_override
                else definition.group_id
            ),
            sort_order=(
                assignment.position if assignment else definition.default_sort_order
            ),
            read_only=read_only,
            value=resolved_value,
            display_value=display,
        )

    @staticmethod
    def _system_value(
        product: Product,
        definition: AttributeDefinition,
        chain: list[Category],
    ) -> Any:
        source = definition.source_path or ""
        product_fields = {
            "Product.name": product.name,
            "Product.manufacturer": product.manufacturer,
            "Product.mpn": product.mpn,
            "Product.sku": product.sku,
            "Product.ean": product.ean,
            "Product.code": product.code,
        }
        if source in product_fields:
            return product_fields[source]
        if source == "Category.path":
            return [category.name for category in chain]
        if source.startswith("Category.path["):
            try:
                index = int(source.removeprefix("Category.path[").removesuffix("]"))
            except ValueError:
                return None
            return chain[index].name if len(chain) > index else None
        return None


__all__ = ["AttributeQueryService"]
