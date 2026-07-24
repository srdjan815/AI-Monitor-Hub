from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.models import Job
from app.modules.execution.repository import (
    InvalidJobTransitionError,
    JobIdempotencyConflictError,
    JobRepository,
)
from app.modules.execution.schemas import JobCreate


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JobRepository(session)

    async def enqueue(self, data: JobCreate) -> Job:
        try:
            job = await self.repository.create(data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if data.idempotency_key:
                existing = await self.repository.get_by_idempotency_key(
                    data.idempotency_key
                )
                if existing is not None:
                    try:
                        self.repository.require_same_idempotent_request(
                            existing,
                            data,
                        )
                    except JobIdempotencyConflictError as conflict:
                        raise HTTPException(
                            status_code=409,
                            detail=str(conflict),
                        ) from conflict
                    return existing
            raise HTTPException(status_code=409, detail="Job conflict") from exc
        except JobIdempotencyConflictError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(job)
        return job

    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.repository.get(job_id)

    async def cancel(self, job_id: uuid.UUID) -> Job:
        try:
            job = await self.repository.get_for_update(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            await self.repository.cancel(job)
            await self.session.commit()
        except InvalidJobTransitionError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(job)
        return job

    async def retry(self, job_id: uuid.UUID) -> Job:
        try:
            job = await self.repository.get_for_update(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job not found")
            await self.repository.retry(job)
            await self.session.commit()
        except InvalidJobTransitionError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(job)
        return job

    async def list(
        self,
        *,
        status: str | None,
        queue: str | None,
        limit: int,
        offset: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Job], int]:
        return await self.repository.list(
            status=status,
            queue=queue,
            limit=limit,
            offset=offset,
            snapshot_at=snapshot_at,
            after=after,
        )
