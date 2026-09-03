from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TypeVar, overload

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product_content.models import (
    ContentChangeEvent,
)
from app.modules.product_content.repositories import ContentRepository

ModelT = TypeVar("ModelT")


def serialize(entity: Any) -> dict[str, Any]:
    return {
        column.name: getattr(entity, column.name) for column in entity.__table__.columns
    }


def validate_schedule(
    publish_at: datetime | None,
    expire_at: datetime | None,
) -> None:
    if publish_at and expire_at and expire_at <= publish_at:
        raise HTTPException(
            status_code=422,
            detail="expire_at must be after publish_at",
        )


class ServiceBase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ContentRepository(session)

    async def required(
        self,
        model: type[ModelT],
        entity_id: uuid.UUID,
        label: str,
    ) -> ModelT:
        entity = await self.repository.get(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        return entity

    async def required_for_update(
        self,
        model: type[ModelT],
        entity_id: uuid.UUID,
        label: str,
    ) -> ModelT:
        entity = await self.repository.get_for_update(model, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        return entity

    @overload
    async def commit(self, entity: ModelT) -> ModelT: ...

    @overload
    async def commit(self) -> None: ...

    async def commit(self, entity: ModelT | None = None) -> ModelT | None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Content constraint conflict",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        if entity is not None:
            await self.session.refresh(entity)
        return entity

    async def mutate(self, entity: ModelT) -> ModelT:
        try:
            await self.repository.add(entity)
            result = await self.commit(entity)
            assert result is not None
            return result
        except HTTPException:
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Content constraint conflict",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def event(
        self,
        entity: Any,
        action: str,
        product_id: uuid.UUID | None = None,
    ) -> None:
        await self.repository.add(
            ContentChangeEvent(
                entity_type=entity.__class__.__name__,
                entity_id=entity.id,
                product_id=product_id,
                action=action,
            )
        )

    async def mutate_with_event(
        self,
        entity: ModelT,
        action: str,
        product_id: uuid.UUID,
    ) -> ModelT:
        try:
            await self.repository.add(entity)
            await self.event(entity, action, product_id)
            result = await self.commit(entity)
            assert result is not None
            return result
        except HTTPException:
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Content constraint conflict",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise


def usage_payload(
    entity_id: uuid.UUID,
    rows: list[Any],
    kind: str,
    reference: str | None = None,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "kind": kind,
        "reference": reference,
        "usage_count": len({row.product_id for row in rows}),
        "products": sorted({row.product_id for row in rows}, key=str),
        "languages": sorted(
            {row.language_id for row in rows if getattr(row, "language_id", None)},
            key=str,
        ),
        "last_usage": max((row.updated_at for row in rows), default=None),
    }
