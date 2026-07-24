from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

from app.core.security import current_actor_id
from app.modules.catalog.attribute_models import (
    ProductAttributeValue,
    ProductAttributeValueHistory,
)
from app.modules.catalog.attribute_query_service import AttributeQueryService
from app.modules.catalog.enums import (
    ApprovalStatus,
    AttributeHistoryAction,
    AttributeScope,
    AttributeSourceType,
    AttributeStorageKind,
    ValidationStatus,
)
from app.modules.catalog.models import (
    AttributeDefinition,
    Product,
)
from app.modules.catalog.schemas.product_attributes import (
    ApprovalRequest,
    BulkValueWrite,
    ProductAttributeValueWrite,
    ResolvedAttribute,
    ResolvedAttributePage,
    ValidationResult,
)

from app.modules.catalog.attribute_service_support import ProductAttributeServiceSupport


class ProductAttributeValueService(ProductAttributeServiceSupport):
    async def resolved_layout(
        self, category_id: uuid.UUID, *, product: Product | None = None
    ) -> list[ResolvedAttribute]:
        return await AttributeQueryService(self.session).resolved_layout(
            category_id,
            product=product,
        )

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
        return await AttributeQueryService(self.session).resolved_page(
            category_id,
            product=product,
            include_unset=include_unset,
            scope=scope,
            group_id=group_id,
            family_id=family_id,
            template_id=template_id,
            limit=limit,
            cursor=cursor,
            filter_only=filter_only,
            compatibility_only=compatibility_only,
        )

    async def validate_value(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        data: ProductAttributeValueWrite,
    ) -> ValidationResult:
        product = await self._required(Product, product_id, "Product")
        definition = await self._required(
            AttributeDefinition, attribute_id, "Attribute definition"
        )
        if definition.storage_kind in {
            AttributeStorageKind.CORE_FIELD.value,
            AttributeStorageKind.RELATION.value,
            AttributeStorageKind.CATEGORY_PATH.value,
        }:
            raise HTTPException(
                status_code=409,
                detail="System-backed attributes are read-only",
            )
        chain = await self.repository.list_category_chain(product.category_id)
        applies_by_scope = definition.scope in {
            AttributeScope.GLOBAL.value,
            AttributeScope.SYSTEM.value,
        }
        applies_by_assignment = await self.repository.has_active_assignment(
            [category.id for category in chain],
            definition.id,
        )
        if not definition.is_active or not (applies_by_scope or applies_by_assignment):
            raise HTTPException(
                status_code=409, detail="Attribute does not apply to product"
            )
        return self.validator.normalize(
            definition,
            data.raw_value,
            unit=data.unit,
            options=await self.repository.list_options(attribute_id),
            rules=await self.repository.list_rules(attribute_id),
        )

    async def write_value(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        data: ProductAttributeValueWrite,
        *,
        commit: bool = True,
    ) -> ProductAttributeValue:
        definition = await self._required(
            AttributeDefinition, attribute_id, "Attribute definition"
        )
        if data.value_key != "single" and not definition.allows_multiple:
            raise HTTPException(
                status_code=409, detail="Attribute does not allow multiple values"
            )
        result = await self.validate_value(product_id, attribute_id, data)
        if (
            result.validation_status == ValidationStatus.INVALID
            and not data.allow_invalid_for_review
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Attribute value is invalid",
                    "errors": result.validation_messages,
                },
            )
        existing = await self.repository.value(product_id, attribute_id, data.value_key)
        if existing is not None and existing.is_locked:
            raise HTTPException(
                status_code=409,
                detail="Attribute value is locked; explicitly unlock it first",
            )
        previous_raw = existing.raw_value if existing else None
        previous_canonical = existing.canonical_value if existing else None
        fields = {
            "raw_value": data.raw_value,
            "canonical_value": result.canonical_value or data.raw_value,
            "display_value": result.display_value or str(data.raw_value),
            "unit": result.normalized_unit,
            "text_value": result.text_value,
            "numeric_value": result.numeric_value,
            "boolean_value": result.boolean_value,
            "date_value": result.date_value,
            "datetime_value": result.datetime_value,
            "json_value": result.json_value,
            "source_type": data.source_type.value,
            "source_reference": data.source_reference,
            "confidence_score": data.confidence_score,
            "validation_status": result.validation_status.value,
            "approval_status": data.approval_status.value,
            "validation_message": "; ".join(result.validation_messages) or None,
            "position": data.position,
        }
        if existing:
            fields["version"] = existing.version + 1
            value = await self.repository.mutate(existing, fields)
            action = AttributeHistoryAction.UPDATED.value
        else:
            value = await self.repository.add(
                ProductAttributeValue(
                    product_id=product_id,
                    attribute_definition_id=attribute_id,
                    value_key=data.value_key,
                    **fields,
                )
            )
            action = AttributeHistoryAction.CREATED.value
        await self.repository.add(
            ProductAttributeValueHistory(
                product_id=product_id,
                attribute_definition_id=attribute_id,
                product_attribute_value_id=value.id,
                action=action,
                previous_raw_value=previous_raw,
                previous_canonical_value=previous_canonical,
                new_raw_value=value.raw_value,
                new_canonical_value=value.canonical_value,
                source_type=value.source_type,
                source_reference=value.source_reference,
                confidence_score=value.confidence_score,
            )
        )
        await self._event(
            "PRODUCT_ATTRIBUTE_VALUE",
            value.id,
            action,
            product_id=product_id,
            metadata={"attribute_id": str(attribute_id)},
        )
        if (
            data.source_type != AttributeSourceType.SYSTEM
            and self.recalculate is not None
        ):
            await self.recalculate(product_id, attribute_id)
        if commit:
            return await self._commit(value)
        return value

    async def bulk_write(
        self, product_id: uuid.UUID, data: BulkValueWrite
    ) -> list[ProductAttributeValue]:
        results: list[ProductAttributeValue] = []
        try:
            for item in data.items:
                payload = ProductAttributeValueWrite(
                    **item.model_dump(exclude={"attribute_id"})
                )
                results.append(
                    await self.write_value(
                        product_id, item.attribute_id, payload, commit=False
                    )
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        for result in results:
            await self.session.refresh(result)
        return results

    async def change_approval(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        approved: bool,
        data: ApprovalRequest,
    ) -> ProductAttributeValue:
        values = await self.repository.values(product_id, attribute_id)
        if not values:
            raise HTTPException(status_code=404, detail="Attribute value not found")
        value = values[0]
        action = (
            AttributeHistoryAction.APPROVED
            if approved
            else AttributeHistoryAction.REJECTED
        )
        actor = current_actor_id() or data.actor
        await self.repository.mutate(
            value,
            {
                "approval_status": (
                    ApprovalStatus.APPROVED.value
                    if approved
                    else ApprovalStatus.REJECTED.value
                ),
                "approved_by": actor if approved else None,
                "approved_at": datetime.now(UTC) if approved else None,
                "validation_message": data.reason or value.validation_message,
                "version": value.version + 1,
            },
        )
        await self.repository.add(
            ProductAttributeValueHistory(
                product_id=product_id,
                attribute_definition_id=attribute_id,
                product_attribute_value_id=value.id,
                action=action.value,
                previous_raw_value=value.raw_value,
                previous_canonical_value=value.canonical_value,
                new_raw_value=value.raw_value,
                new_canonical_value=value.canonical_value,
                source_type=value.source_type,
                source_reference=value.source_reference,
                confidence_score=value.confidence_score,
                actor_identifier=actor,
            )
        )
        await self._event(
            "PRODUCT_ATTRIBUTE_VALUE",
            value.id,
            action.value,
            product_id=product_id,
        )
        return await self._commit(value)

    async def deactivate_value(
        self, product_id: uuid.UUID, attribute_id: uuid.UUID
    ) -> None:
        values = await self.repository.values(product_id, attribute_id)
        if not values:
            raise HTTPException(status_code=404, detail="Attribute value not found")
        for value in values:
            await self.repository.mutate(
                value, {"is_active": False, "version": value.version + 1}
            )
            await self.repository.add(
                ProductAttributeValueHistory(
                    product_id=product_id,
                    attribute_definition_id=attribute_id,
                    product_attribute_value_id=value.id,
                    action=AttributeHistoryAction.DEACTIVATED.value,
                    previous_raw_value=value.raw_value,
                    previous_canonical_value=value.canonical_value,
                    source_type=value.source_type,
                    source_reference=value.source_reference,
                    confidence_score=value.confidence_score,
                )
            )
            await self._event(
                "PRODUCT_ATTRIBUTE_VALUE",
                value.id,
                "DEACTIVATED",
                product_id=product_id,
            )
        await self._commit()


__all__ = ["ProductAttributeValueService"]
