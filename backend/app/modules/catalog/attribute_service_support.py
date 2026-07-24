from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, overload

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.attribute_models import (
    AttributeChangeEvent,
)
from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_validation import AttributeValueValidator

ModelT = TypeVar("ModelT")


class ProductAttributeServiceSupport:
    def __init__(
        self,
        session: AsyncSession,
        recalculate: Callable[[uuid.UUID, uuid.UUID], Awaitable[None]] | None = None,
    ) -> None:
        self.session = session
        self.repository = ProductAttributeRepository(session)
        self.validator = AttributeValueValidator()
        self.recalculate = recalculate

    async def dashboard(self) -> dict[str, int | None]:
        return await self.repository.dashboard()

    @overload
    async def _commit(self, entity: ModelT) -> ModelT: ...

    @overload
    async def _commit(self) -> None: ...

    async def _commit(self, entity: ModelT | None = None) -> ModelT | None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Unique or state constraint conflict"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        if entity is not None:
            await self.session.refresh(entity)
        return entity

    async def _required(
        self, model: type[ModelT], entity_id: uuid.UUID, name: str
    ) -> ModelT:
        entity = await self.repository.get(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{name} not found")
        return entity

    async def _event(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        *,
        product_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AttributeChangeEvent:
        return await self.repository.add(
            AttributeChangeEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                product_id=product_id,
                action=action,
                event_metadata=metadata or {},
            )
        )


__all__ = ["ProductAttributeServiceSupport"]
