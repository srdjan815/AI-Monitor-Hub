from __future__ import annotations

import uuid
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


ModelT = TypeVar("ModelT")


class ContentRepositorySupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, model: type[ModelT], entity_id: uuid.UUID) -> ModelT | None:
        return await self.session.get(model, entity_id)

    async def get_for_update(
        self,
        model: type[ModelT],
        entity_id: uuid.UUID,
    ) -> ModelT | None:
        return await self.session.get(model, entity_id, with_for_update=True)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: Any) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def flush(self) -> None:
        await self.session.flush()

    async def all(self, query: Select[tuple[ModelT]]) -> list[ModelT]:
        return list((await self.session.scalars(query)).all())

    async def one(self, query: Select[tuple[ModelT]]) -> ModelT | None:
        return (await self.session.scalars(query)).first()

    async def _revision_page(
        self,
        model: type[Any],
        criterion: Any,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
        revision_column: Any | None = None,
    ) -> tuple[list[Any], int]:
        column = revision_column if revision_column is not None else model.revision
        if snapshot_revision is None:
            snapshot_revision = int(
                await self.session.scalar(select(func.max(column)).where(criterion))
                or 0
            )
        query = select(model).where(
            criterion,
            column <= snapshot_revision,
        )
        if after_revision is not None:
            query = query.where(column < after_revision)
        rows = await self.all(
            query.order_by(column.desc(), model.id.desc()).limit(limit)
        )
        return rows, snapshot_revision


__all__ = ["ContentRepositorySupport"]
