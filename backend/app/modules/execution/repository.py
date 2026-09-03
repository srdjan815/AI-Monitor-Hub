from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_actor_id
from app.modules.execution.enums import JobStatus
from app.modules.execution.models import Job, JobAttempt
from app.modules.execution.schemas import JobCreate


RETRY_BASE_SECONDS = 5
RETRY_MAX_SECONDS = 300
RETRY_JITTER_RATIO = 0.20
TERMINAL_STATUSES = frozenset(
    {
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.DEAD_LETTER.value,
    }
)


def retry_delay_seconds(job_id: uuid.UUID, attempt: int) -> float:
    """Return bounded deterministic exponential backoff with +/- 20% jitter."""

    exponential = float(RETRY_BASE_SECONDS * pow(2, max(attempt - 1, 0)))
    digest = hashlib.blake2s(
        f"{job_id}:{attempt}".encode(),
        digest_size=2,
    ).digest()
    unit_interval = int.from_bytes(digest) / 65_535
    factor = 1 - RETRY_JITTER_RATIO + (2 * RETRY_JITTER_RATIO * unit_interval)
    delay: float = min(float(RETRY_MAX_SECONDS), exponential * factor)
    return delay


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: JobCreate) -> Job:
        if data.idempotency_key:
            existing = await self.get_by_idempotency_key(data.idempotency_key)
            if existing is not None:
                self.require_same_idempotent_request(existing, data)
                return existing

        job = Job(
            job_type=data.job_type,
            queue=data.queue,
            priority=data.priority,
            payload=data.payload,
            max_attempts=data.max_attempts,
            available_at=data.available_at or datetime.now(UTC),
            idempotency_key=data.idempotency_key,
            correlation_id=data.correlation_id or uuid.uuid4(),
            created_by=current_actor_id() or data.created_by,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    @staticmethod
    def require_same_idempotent_request(existing: Job, data: JobCreate) -> None:
        expected_actor = current_actor_id() or data.created_by
        mismatched = (
            existing.job_type != data.job_type
            or existing.queue != data.queue
            or existing.priority != data.priority
            or existing.payload != data.payload
            or existing.max_attempts != data.max_attempts
            or existing.created_by != expected_actor
            or (
                data.correlation_id is not None
                and existing.correlation_id != data.correlation_id
            )
            or (
                data.available_at is not None
                and existing.available_at != data.available_at
            )
        )
        if mismatched:
            raise JobIdempotencyConflictError(
                "Idempotency key was already used for a different job request"
            )

    async def cancel(self, job: Job) -> bool:
        if job.status == JobStatus.CANCELLED.value:
            return False
        if job.status in TERMINAL_STATUSES:
            raise InvalidJobTransitionError(f"Cannot cancel job in {job.status} state")
        if job.status not in {
            JobStatus.PENDING.value,
            JobStatus.RETRYING.value,
            JobStatus.RUNNING.value,
        }:
            raise InvalidJobTransitionError(
                f"Unsupported cancellation from {job.status} state"
            )

        was_running = job.status == JobStatus.RUNNING.value
        job.status = JobStatus.CANCELLED.value
        job.finished_at = datetime.now(UTC)
        job.locked_by = None
        job.locked_at = None
        job.lease_token = None
        job.error_code = "CANCELLED"
        job.error_message = "Job cancelled by operator"
        job.version += 1
        if was_running:
            await self._finish_attempt(
                job,
                JobStatus.CANCELLED.value,
                error_code="CANCELLED",
                error_message="Job cancelled by operator",
            )
        await self.session.flush()
        return True

    async def retry(self, job: Job) -> None:
        if job.status not in {
            JobStatus.FAILED.value,
            JobStatus.DEAD_LETTER.value,
        }:
            raise InvalidJobTransitionError(f"Cannot retry job in {job.status} state")

        if job.attempt >= job.max_attempts:
            job.max_attempts = job.attempt + 1
        job.status = JobStatus.RETRYING.value
        job.available_at = datetime.now(UTC)
        job.finished_at = None
        job.locked_by = None
        job.locked_at = None
        job.lease_token = None
        job.result = None
        job.error_code = None
        job.error_message = None
        job.version += 1
        await self.session.flush()

    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def get_for_update(self, job_id: uuid.UUID) -> Job | None:
        result = await self.session.execute(
            select(Job).where(Job.id == job_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Job | None:
        result = await self.session.execute(
            select(Job).where(Job.idempotency_key == key)
        )
        return result.scalar_one_or_none()

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
        filters = []
        if status:
            filters.append(Job.status == status)
        if queue:
            filters.append(Job.queue == queue)
        if snapshot_at is not None:
            filters.append(Job.created_at <= snapshot_at)

        count_query = select(func.count()).select_from(Job).where(*filters)
        page_filters = list(filters)
        if after is not None:
            after_at, after_id = after
            page_filters.append(
                or_(
                    Job.created_at < after_at,
                    and_(
                        Job.created_at == after_at,
                        Job.id < after_id,
                    ),
                )
            )

        query: Select[tuple[Job]] = select(Job).where(*page_filters)
        query = (
            query.order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )

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
            .order_by(Job.priority.asc(), Job.created_at.asc(), Job.id.asc())
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
        job.lease_token = uuid.uuid4()
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

    async def heartbeat(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        lease_token: uuid.UUID,
        attempt: int,
    ) -> bool:
        result = await self.session.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == JobStatus.RUNNING.value,
                Job.locked_by == worker_id,
                Job.lease_token == lease_token,
                Job.attempt == attempt,
            )
            .values(locked_at=datetime.now(UTC))
        )
        return bool(getattr(result, "rowcount", 0))

    @staticmethod
    def require_lease(
        job: Job,
        *,
        worker_id: str,
        lease_token: uuid.UUID,
        attempt: int,
    ) -> None:
        if (
            job.status != JobStatus.RUNNING.value
            or job.locked_by != worker_id
            or job.lease_token != lease_token
            or job.attempt != attempt
        ):
            raise JobLeaseLostError("Job lease is no longer owned by this worker")

    async def mark_succeeded(
        self,
        job: Job,
        result: dict,
        *,
        worker_id: str,
        lease_token: uuid.UUID,
        attempt: int,
    ) -> None:
        self.require_lease(
            job,
            worker_id=worker_id,
            lease_token=lease_token,
            attempt=attempt,
        )
        now = datetime.now(UTC)
        job.status = JobStatus.SUCCEEDED.value
        job.result = result
        job.finished_at = now
        job.locked_by = None
        job.locked_at = None
        job.lease_token = None
        job.error_code = None
        job.error_message = None
        job.version += 1
        await self._finish_attempt(job, JobStatus.SUCCEEDED.value)
        await self.session.flush()

    async def mark_failed(
        self,
        job: Job,
        *,
        error_code: str,
        error_message: str,
        worker_id: str,
        lease_token: uuid.UUID,
        attempt: int,
        retryable: bool = True,
    ) -> None:
        self.require_lease(
            job,
            worker_id=worker_id,
            lease_token=lease_token,
            attempt=attempt,
        )
        now = datetime.now(UTC)
        exhausted = job.attempt >= job.max_attempts
        if not retryable:
            job.status = JobStatus.FAILED.value
        elif exhausted:
            job.status = JobStatus.DEAD_LETTER.value
        else:
            job.status = JobStatus.RETRYING.value
        job.error_code = error_code
        job.error_message = error_message[:4000]
        job.locked_by = None
        job.locked_at = None
        job.lease_token = None
        job.finished_at = now if job.status in TERMINAL_STATUSES else None
        if job.status == JobStatus.RETRYING.value:
            delay_seconds = retry_delay_seconds(job.id, job.attempt)
            job.available_at = now + timedelta(seconds=delay_seconds)
        job.version += 1
        await self._finish_attempt(
            job, job.status, error_code=error_code, error_message=error_message
        )
        await self.session.flush()

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
            await self._transition_stale_job(
                job,
                error_code="STALE_LOCK",
                error_message="Worker lock expired before completion",
            )
        await self.session.flush()
        return len(jobs)

    async def _transition_stale_job(
        self,
        job: Job,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        """Recover a locked row without pretending the recovery owns its lease."""

        now = datetime.now(UTC)
        exhausted = job.attempt >= job.max_attempts
        job.status = (
            JobStatus.DEAD_LETTER.value if exhausted else JobStatus.RETRYING.value
        )
        job.error_code = error_code
        job.error_message = error_message
        job.locked_by = None
        job.locked_at = None
        job.lease_token = None
        job.finished_at = now if exhausted else None
        if not exhausted:
            job.available_at = now + timedelta(
                seconds=retry_delay_seconds(job.id, job.attempt)
            )
        job.version += 1
        await self._finish_attempt(
            job,
            job.status,
            error_code=error_code,
            error_message=error_message,
        )

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


class JobLeaseLostError(RuntimeError):
    """Raised when a stale worker attempts to mutate a newer job attempt."""


class InvalidJobTransitionError(ValueError):
    """Raised when a requested job state transition is not legal."""


class JobIdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused with different semantics."""
