from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.modules.catalog.attribute_models import (
    ProductAttributeValue,
    ProductAttributeValueHistory,
)
from app.modules.catalog.enums import AttributeSourceType
from app.modules.catalog.models import Product
from app.modules.catalog.platform_models import AttributeFormula
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import (
    EnterpriseBulkWrite,
    LockRequest,
)
from app.modules.catalog.schemas.product_attributes import (
    ProductAttributeValueWrite,
)


class AttributeValueMutationService(_PlatformServiceSupport):
    """Owns formula recalculation, value locking, and atomic bulk writes."""

    async def recalculate_product(
        self,
        product_id: uuid.UUID,
        *,
        changed_attribute_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> list[ProductAttributeValue]:
        await self._required(Product, product_id, "Product")
        definitions = {
            item.id: item
            for item in await self.repository.list_definitions(active_only=True)
        }
        records = await self.repository.values(product_id)
        values = {
            definitions[item.attribute_definition_id].api_name: (
                item.numeric_value
                if item.numeric_value is not None
                else item.canonical_value
            )
            for item in records
            if item.attribute_definition_id in definitions
        }
        formulas = list(
            (
                await self.session.execute(
                    select(AttributeFormula).where(AttributeFormula.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        changed_name = (
            definitions[changed_attribute_id].api_name
            if changed_attribute_id in definitions
            else None
        )
        written: list[ProductAttributeValue] = []
        pending = formulas[:]
        for _ in range(len(formulas) + 1):
            progress = False
            for formula in pending[:]:
                target = definitions.get(formula.target_attribute_id)
                if target is None:
                    pending.remove(formula)
                    continue
                dependencies = self.formulas.dependencies(formula.expression)
                if (
                    changed_name
                    and changed_name not in dependencies
                    and not (dependencies & set(values))
                ):
                    continue
                if not dependencies <= values.keys():
                    continue
                result = self.formulas.evaluate(
                    formula.expression,
                    values,
                )
                record = await self.attributes.write_value(
                    product_id,
                    target.id,
                    ProductAttributeValueWrite(
                        raw_value=str(result),
                        source_type=AttributeSourceType.SYSTEM,
                        source_reference=f"formula:{formula.id}",
                    ),
                    commit=False,
                )
                values[target.api_name] = result
                written.append(record)
                pending.remove(formula)
                progress = True
            if not progress:
                break
        if commit:
            await self._commit()
            for record in written:
                await self.session.refresh(record)
        return written

    async def lock_value(
        self,
        product_id: uuid.UUID,
        attribute_id: uuid.UUID,
        data: LockRequest,
        locked: bool,
    ) -> ProductAttributeValue:
        records = await self.repository.values(product_id, attribute_id)
        if not records:
            raise HTTPException(
                status_code=404,
                detail="Attribute value not found",
            )
        record = records[0]
        record.is_locked = locked
        record.locked_by = data.actor if locked else None
        record.locked_at = datetime.now(UTC) if locked else None
        record.lock_reason = data.reason if locked else None
        record.version += 1
        await self.session.flush()
        await self.attributes.repository.add(
            ProductAttributeValueHistory(
                product_id=product_id,
                attribute_definition_id=attribute_id,
                product_attribute_value_id=record.id,
                action="LOCKED" if locked else "UNLOCKED",
                previous_raw_value=record.raw_value,
                previous_canonical_value=record.canonical_value,
                new_raw_value=record.raw_value,
                new_canonical_value=record.canonical_value,
                source_type=record.source_type,
                source_reference=record.source_reference,
                confidence_score=record.confidence_score,
                actor_identifier=data.actor,
            )
        )
        await self.attributes._event(
            "PRODUCT_ATTRIBUTE_VALUE",
            record.id,
            "LOCKED" if locked else "UNLOCKED",
            product_id=product_id,
        )
        return await self._commit(record)

    async def bulk_update(
        self,
        data: EnterpriseBulkWrite,
        *,
        preview: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            for item in data.items:
                payload = ProductAttributeValueWrite(
                    raw_value=item.raw_value,
                    unit=item.unit,
                    value_key=item.value_key,
                    source_type=AttributeSourceType.MANUAL,
                )
                validation = await self.attributes.validate_value(
                    item.product_id,
                    item.attribute_id,
                    payload,
                )
                results.append(
                    {
                        "product_id": item.product_id,
                        "attribute_id": item.attribute_id,
                        "validation": validation.model_dump(mode="json"),
                    }
                )
                if not preview:
                    await self.attributes.write_value(
                        item.product_id,
                        item.attribute_id,
                        payload,
                        commit=False,
                    )
            if preview:
                await self.session.rollback()
            else:
                await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return results
