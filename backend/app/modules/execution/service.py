from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.models import Job
from app.modules.execution.repository import JobRepository
from app.modules.execution.schemas import JobCreate

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JobRepository(session)

    async def enqueue(self, data: JobCreate) -> Job:
        job = await self.repository.create(data)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.repository.get(job_id)
