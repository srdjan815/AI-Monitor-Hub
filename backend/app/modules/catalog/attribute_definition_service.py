from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

from app.modules.catalog.attribute_models import (
    AttributeGroup,
)
from app.modules.catalog.enums import (
    AttributeStatus,
)
from app.modules.catalog.models import (
    AttributeDefinition,
)
from app.modules.catalog.schemas.product_attributes import (
    AttributeDefinitionCreate,
    AttributeDefinitionUpdate,
    AttributeGroupCreate,
    AttributeGroupUpdate,
    ReorderRequest,
)
from app.modules.catalog.utils import stable_code

from app.modules.catalog.attribute_service_support import ProductAttributeServiceSupport


class AttributeDefinitionService(ProductAttributeServiceSupport):
    async def create_group(self, data: AttributeGroupCreate) -> AttributeGroup:
        slug = stable_code(data.slug or data.name)
        if await self.repository.group_by_slug(slug):
            raise HTTPException(status_code=409, detail="Group slug already exists")
        group = AttributeGroup(
            name=data.name.strip(),
            slug=slug,
            description=data.description,
            sort_order=data.sort_order,
        )
        await self.repository.add(group)
        await self._event("ATTRIBUTE_GROUP", group.id, "CREATED")
        return await self._commit(group)

    async def update_group(
        self, group_id: uuid.UUID, data: AttributeGroupUpdate
    ) -> AttributeGroup:
        group = await self._required(AttributeGroup, group_id, "Attribute group")
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
        actual = {
            key: value for key, value in changes.items() if getattr(group, key) != value
        }
        if actual:
            actual["version"] = group.version + 1
            await self.repository.mutate(group, actual)
            await self._event("ATTRIBUTE_GROUP", group.id, "UPDATED")
        return await self._commit(group)

    async def deactivate_group(self, group_id: uuid.UUID) -> None:
        group = await self._required(AttributeGroup, group_id, "Attribute group")
        if group.is_active:
            await self.repository.mutate(
                group, {"is_active": False, "version": group.version + 1}
            )
            await self._event("ATTRIBUTE_GROUP", group.id, "DEACTIVATED")
        await self._commit()

    async def reorder_groups(self, data: ReorderRequest) -> list[AttributeGroup]:
        for item in data.items:
            group = await self._required(AttributeGroup, item.id, "Attribute group")
            await self.repository.mutate(
                group,
                {"sort_order": item.sort_order, "version": group.version + 1},
            )
            await self._event("ATTRIBUTE_GROUP", group.id, "REORDERED")
        await self._commit()
        return await self.repository.list_groups(active_only=False)

    async def create_definition(
        self, data: AttributeDefinitionCreate
    ) -> AttributeDefinition:
        slug = stable_code(data.slug or data.name)
        internal_name = stable_code(data.internal_name or slug)
        api_name = stable_code(data.api_name or slug)
        for value in {slug, internal_name, api_name}:
            if await self.repository.definition_by_identity(value):
                raise HTTPException(
                    status_code=409, detail="Definition identity already exists"
                )
        if data.group_id:
            await self._required(AttributeGroup, data.group_id, "Attribute group")
        attribute = AttributeDefinition(
            name=data.name.strip(),
            code=slug,
            slug=slug,
            internal_name=internal_name,
            api_name=api_name,
            description=data.description,
            tooltip=data.tooltip,
            group_id=data.group_id,
            scope=data.scope.value,
            storage_kind=data.storage_kind.value,
            data_type=data.data_type.value,
            status=data.status.value,
            source_path=data.source_path,
            default_sort_order=data.default_sort_order,
            show_in_admin=data.show_in_admin,
            show_on_webshop=data.show_on_webshop,
            show_in_mini_specification=data.show_in_mini_specification,
            show_in_full_specification=data.show_in_full_specification,
            is_searchable=data.is_searchable,
            is_required=data.is_required_by_default,
            allows_multiple=data.allow_multiple_values,
            minimum_value=data.minimum_value,
            maximum_value=data.maximum_value,
            minimum_length=data.minimum_length,
            maximum_length=data.maximum_length,
            regex_pattern=data.regex_pattern,
            unit=data.default_unit,
            default_unit=data.default_unit,
            accepted_units=data.accepted_units,
            default_value=data.default_value,
            validation_message=data.validation_message,
            is_filterable=data.is_filter,
            filter_type=data.filter_type.value if data.filter_type else None,
            filter_sort_order=data.filter_sort_order,
            is_compatibility_attribute=data.is_compatibility_attribute,
            compatibility_type=data.compatibility_type,
            compatibility_priority=data.compatibility_priority,
            use_ai=data.use_ai,
            extraction_prompt=data.extraction_prompt,
            normalization_prompt=data.normalization_prompt,
            validation_prompt=data.validation_prompt,
            confidence_threshold=data.confidence_threshold,
            examples=data.examples,
            forbidden_values=data.forbidden_values,
            is_active=data.status != AttributeStatus.INACTIVE,
        )
        await self.repository.add(attribute)
        await self._event("ATTRIBUTE_DEFINITION", attribute.id, "CREATED")
        return await self._commit(attribute)

    async def update_definition(
        self, attribute_id: uuid.UUID, data: AttributeDefinitionUpdate
    ) -> AttributeDefinition:
        definition = await self._required(
            AttributeDefinition, attribute_id, "Attribute definition"
        )
        changes = data.model_dump(exclude_unset=True)
        aliases = {
            "is_required_by_default": "is_required",
            "allow_multiple_values": "allows_multiple",
            "is_filter": "is_filterable",
        }
        changes = {aliases.get(key, key): value for key, value in changes.items()}
        for key in ("status", "filter_type"):
            if key in changes and changes[key] is not None:
                changes[key] = changes[key].value
        if changes.get("group_id"):
            await self._required(AttributeGroup, changes["group_id"], "Attribute group")
        minimum_value = changes.get("minimum_value", definition.minimum_value)
        maximum_value = changes.get("maximum_value", definition.maximum_value)
        if (
            minimum_value is not None
            and maximum_value is not None
            and minimum_value > maximum_value
        ):
            raise HTTPException(status_code=422, detail="Invalid minimum/maximum")
        actual = {
            key: value
            for key, value in changes.items()
            if getattr(definition, key) != value
        }
        if actual:
            actual["version"] = definition.version + 1
            if actual.get("is_active") is False:
                actual["deactivated_at"] = datetime.now(UTC)
            await self.repository.mutate(definition, actual)
            await self._event("ATTRIBUTE_DEFINITION", definition.id, "UPDATED")
        return await self._commit(definition)

    async def deactivate_definition(self, attribute_id: uuid.UUID) -> None:
        await self.update_definition(
            attribute_id, AttributeDefinitionUpdate(is_active=False)
        )

    async def reorder_definitions(
        self, data: ReorderRequest
    ) -> list[AttributeDefinition]:
        for item in data.items:
            definition = await self._required(
                AttributeDefinition, item.id, "Attribute definition"
            )
            await self.repository.mutate(
                definition,
                {
                    "default_sort_order": item.sort_order,
                    "version": definition.version + 1,
                },
            )
            await self._event("ATTRIBUTE_DEFINITION", definition.id, "REORDERED")
        await self._commit()
        return await self.repository.list_definitions(active_only=False)


__all__ = ["AttributeDefinitionService"]
