from __future__ import annotations

import uuid
from typing import TypeVar, overload

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.attribute_repository import ProductAttributeRepository
from app.modules.catalog.attribute_service import ProductAttributeService
from app.modules.catalog.formula_engine import FormulaEngine


ModelT = TypeVar("ModelT")


class _PlatformServiceSupport:
    """Shared transaction and lookup support for attribute platform services."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProductAttributeRepository(session)
        self.attributes = ProductAttributeService(session)
        self.formulas = FormulaEngine()

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
                status_code=409,
                detail="Platform conflict",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        if entity is not None:
            await self.session.refresh(entity)
        return entity

    async def _required(
        self,
        model: type[ModelT],
        entity_id: uuid.UUID,
        name: str,
    ) -> ModelT:
        entity = await self.session.get(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{name} not found")
        return entity
