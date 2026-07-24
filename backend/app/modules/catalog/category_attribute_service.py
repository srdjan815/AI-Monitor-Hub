from __future__ import annotations

import uuid

from fastapi import HTTPException

from app.modules.catalog.attribute_models import (
    AttributeGroup,
)
from app.modules.catalog.models import (
    AttributeDefinition,
    Category,
    CategoryAttribute,
)
from app.modules.catalog.schemas.product_attributes import (
    CategoryAssignmentCreate,
    CategoryAssignmentUpdate,
    ReorderRequest,
)

from app.modules.catalog.attribute_service_support import ProductAttributeServiceSupport


class CategoryAttributeService(ProductAttributeServiceSupport):
    async def create_assignment(
        self, category_id: uuid.UUID, data: CategoryAssignmentCreate
    ) -> CategoryAttribute:
        await self._required(Category, category_id, "Category")
        await self._required(
            AttributeDefinition,
            data.attribute_definition_id,
            "Attribute definition",
        )
        if await self.repository.assignment_for_attribute(
            category_id, data.attribute_definition_id
        ):
            raise HTTPException(status_code=409, detail="Assignment already exists")
        if data.group_id_override:
            await self._required(
                AttributeGroup, data.group_id_override, "Attribute group"
            )
        assignment = CategoryAttribute(
            category_id=category_id,
            attribute_id=data.attribute_definition_id,
            group_id_override=data.group_id_override,
            position=data.sort_order,
            is_required_override=data.is_required_override,
            show_on_webshop_override=data.show_on_webshop_override,
            show_in_mini_specification_override=(
                data.show_in_mini_specification_override
            ),
            show_in_full_specification_override=(
                data.show_in_full_specification_override
            ),
            is_filter_override=data.is_filter_override,
            filter_type_override=(
                data.filter_type_override.value if data.filter_type_override else None
            ),
            is_compatibility_override=data.is_compatibility_override,
            compatibility_priority_override=data.compatibility_priority_override,
        )
        await self.repository.add(assignment)
        await self._event("CATEGORY_ASSIGNMENT", assignment.id, "CREATED")
        return await self._commit(assignment)

    async def update_assignment(
        self,
        category_id: uuid.UUID,
        assignment_id: uuid.UUID,
        data: CategoryAssignmentUpdate,
    ) -> CategoryAttribute:
        assignment = await self.repository.assignment(category_id, assignment_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail="Assignment not found")
        changes = data.model_dump(exclude_unset=True)
        if "sort_order" in changes:
            changes["position"] = changes.pop("sort_order")
        if changes.get("filter_type_override"):
            changes["filter_type_override"] = changes["filter_type_override"].value
        actual = {
            key: value
            for key, value in changes.items()
            if getattr(assignment, key) != value
        }
        if actual:
            actual["version"] = assignment.version + 1
            await self.repository.mutate(assignment, actual)
            await self._event("CATEGORY_ASSIGNMENT", assignment.id, "UPDATED")
        return await self._commit(assignment)

    async def deactivate_assignment(
        self, category_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> None:
        await self.update_assignment(
            category_id,
            assignment_id,
            CategoryAssignmentUpdate(is_active=False),
        )

    async def reorder_assignments(
        self, category_id: uuid.UUID, data: ReorderRequest
    ) -> list[CategoryAttribute]:
        try:
            for item in data.items:
                assignment = await self.repository.assignment(category_id, item.id)
                if assignment is None:
                    raise HTTPException(status_code=404, detail="Assignment not found")
                await self.repository.mutate(
                    assignment,
                    {
                        "position": item.sort_order,
                        "version": assignment.version + 1,
                    },
                )
                await self._event("CATEGORY_ASSIGNMENT", assignment.id, "REORDERED")
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return await self.repository.list_assignments([category_id], active_only=False)


__all__ = ["CategoryAttributeService"]
