from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.enums import JobStatus
from app.modules.execution.models import Job, JobAttempt
from app.modules.execution.schemas import JobCreate


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: JobCreate) -> Job:
        if data.idempotency_key:
            existing = await self.get_by_idempotency_key(data.idempotency_key)
            if existing is not None:
                return existing

        job = Job(
            job_type=data.job_type,
            queue=data.queue,
            priority=data.priority,
            payload=data.payload,
            max_attempts=data.max_attempts,
            idempotency_key=data.idempotency_key,
            correlation_id=data.correlation_id or uuid.uuid4(),
            created_by=data.created_by,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def get_by_idempotency_key(self, key: str) -> Job | None:
        result = await self.session.execute(
            select(Job).where(Job.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def list(self, *, status: str | None, queue: str | None, limit: int, offset: int) -> tuple[list[Job], int]:
        filters = []
        if status:
            filters.append(Job.status == status)
        if queue:
            filters.append(Job.queue == queue)

        query: Select[tuple[Job]] = select(Job).where(*filters)
        query = query.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        count_query = select(func.count()).select_from(Job).where(*filters)

        rows = (await self.session.execute(query)).scalars().all()
        total = int((await self.session.execute(count_query)).scalar_one())
        return list(rows), total

    async def claim_next(self, *, queue: str, worker_id: str) -> Job | None:
        now = datetime.now(UTC)
        query = (
            select(Job)
            .where(
                Job.queue == queue,
                Job.status.in_([JobStatus.PENDING.value, JobStatus.RETRYING.value]),
                Job.available_at <= now,
            )
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = (await self.session.execute(query)).scalar_one_or_none()
        if job is None:
            return None

        job.status = JobStatus.RUNNING.value
        job.locked_by = worker_id
        job.locked_at = now
        job.started_at = job.started_at or now
        job.attempt += 1
        job.version += 1
        self.session.add(
            JobAttempt(
                job_id=job.id,
                attempt_number=job.attempt,
                worker_id=worker_id,
                status=JobStatus.RUNNING.value,
            )
        )
        await self.session.flush()
        return job

    async def mark_succeeded(self, job: Job, result: dict) -> None:
        now = datetime.now(UTC)
        job.status = JobStatus.SUCCEEDED.value
        job.result = result
        job.finished_at = now
        job.locked_by = None
        job.locked_at = None
        job.error_code = None
        job.error_message = None
        job.version += 1
        await self._finish_attempt(job, JobStatus.SUCCEEDED.value)

    async def mark_failed(self, job: Job, *, error_code: str, error_message: str) -> None:
        now = datetime.now(UTC)
        terminal = job.attempt >= job.max_attempts
        job.status = (
            JobStatus.DEAD_LETTER.value if terminal else JobStatus.RETRYING.value
        )
        job.error_code = error_code
        job.error_message = error_message[:4000]
        job.locked_by = None
        job.locked_at = None
        job.finished_at = now if terminal else None
        if not terminal:
            delay_seconds = min(300, 2 ** max(job.attempt - 1, 0) * 5)
            job.available_at = now + timedelta(seconds=delay_seconds)
        job.version += 1
        await self._finish_attempt(
            job, job.status, error_code=error_code, error_message=error_message
        )

    async def recover_stale(self, *, stale_after_seconds: int) -> int:
        threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        result = await self.session.execute(
            select(Job)
            .where(
                Job.status == JobStatus.RUNNING.value,
                Job.locked_at < threshold,
            )
            .with_for_update(skip_locked=True)
        )
        jobs = result.scalars().all()
        for job in jobs:
            await self.mark_failed(
                job,
                error_code="STALE_LOCK",
                error_message="Worker lock expired before completion",
            )
        return len(jobs)

    async def _finish_attempt(
        self,
        job: Job,
        status: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        result = await self.session.execute(
            select(JobAttempt).where(
                JobAttempt.job_id == job.id,
                JobAttempt.attempt_number == job.attempt,
            )
        )
        attempt = result.scalar_one_or_none()
        if attempt:
            attempt.status = status
            attempt.finished_at = datetime.now(UTC)
            attempt.error_code = error_code
            attempt.error_message = error_message[:4000] if error_message else None
