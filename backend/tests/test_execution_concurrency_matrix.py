from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.execution.enums import JobStatus
from app.modules.execution.models import Job, JobAttempt
from app.modules.execution.repository import JobLeaseLostError, JobRepository
from app.modules.execution.schemas import JobCreate
from app.modules.execution.service import JobService


DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@db:5432/ai_content_integration",
)


def session_factory() -> tuple:
    engine = create_async_engine(DATABASE_URL, pool_size=10)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def race(
    first: Callable[[], Awaitable[object]],
    second: Callable[[], Awaitable[object]],
) -> tuple[object, object]:
    start = asyncio.Event()

    async def invoke(operation: Callable[[], Awaitable[object]]) -> object:
        await start.wait()
        try:
            return await operation()
        except Exception as exc:
            return exc

    first_task = asyncio.create_task(invoke(first))
    second_task = asyncio.create_task(invoke(second))
    start.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)
    return first_result, second_result


async def enqueue(sessions, *, queue: str, max_attempts: int = 3) -> Job:
    async with sessions() as session:
        return await JobService(session).enqueue(
            JobCreate(
                job_type="system.health_echo",
                queue=queue,
                max_attempts=max_attempts,
            )
        )


async def claim(sessions, job: Job, worker_id: str) -> tuple[uuid.UUID, int]:
    async with sessions() as session:
        claimed = await JobRepository(session).claim_next(
            queue=job.queue,
            worker_id=worker_id,
        )
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.lease_token is not None
        lease_token = claimed.lease_token
        attempt = claimed.attempt
        await session.commit()
        return lease_token, attempt


async def mark_stale(sessions, job_id: uuid.UUID) -> None:
    async with sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.locked_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.commit()


@pytest.mark.asyncio
async def test_duplicate_idempotent_submission_and_simultaneous_claim_matrix() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            key = f"execution-matrix-{iteration}-{uuid.uuid4().hex}"
            queue = f"execution-claim-{iteration}-{uuid.uuid4().hex}"
            payload = JobCreate(
                job_type="system.health_echo",
                queue=queue,
                payload={"iteration": iteration},
                idempotency_key=key,
            )

            async def submit() -> object:
                async with sessions() as session:
                    return await JobService(session).enqueue(payload)

            submissions = await race(submit, submit)
            assert all(isinstance(item, Job) for item in submissions)
            first_job, second_job = submissions
            assert isinstance(first_job, Job)
            assert isinstance(second_job, Job)
            assert first_job.id == second_job.id
            job_id = first_job.id

            async with sessions() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(Job)
                        .where(Job.idempotency_key == key)
                    )
                    == 1
                )

            async def claim_once(worker_id: str) -> object:
                async with sessions() as session:
                    claimed = await JobRepository(session).claim_next(
                        queue=queue,
                        worker_id=worker_id,
                    )
                    await session.commit()
                    return claimed

            claims = await race(
                lambda: claim_once("worker-a"),
                lambda: claim_once("worker-b"),
            )
            claimed_jobs = [item for item in claims if isinstance(item, Job)]
            assert len(claimed_jobs) == 1
            assert sum(item is None for item in claims) == 1
            assert claimed_jobs[0].id == job_id

            async with sessions() as session:
                attempts = list(
                    (
                        await session.scalars(
                            select(JobAttempt).where(JobAttempt.job_id == job_id)
                        )
                    ).all()
                )
                current = await session.get(Job, job_id)
                assert current is not None
                assert current.status == JobStatus.RUNNING.value
                assert current.attempt == 1
                assert current.version == 2
                assert len(attempts) == 1
                assert attempts[0].status == JobStatus.RUNNING.value
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_heartbeat_recovery_and_recovery_completion_matrix() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            queue = f"heartbeat-recovery-{iteration}-{uuid.uuid4().hex}"
            job = await enqueue(sessions, queue=queue)
            lease_token, attempt = await claim(sessions, job, "heartbeat-worker")
            await mark_stale(sessions, job.id)

            async def heartbeat() -> object:
                async with sessions() as session:
                    refreshed = await JobRepository(session).heartbeat(
                        job_id=job.id,
                        worker_id="heartbeat-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                    await session.commit()
                    return refreshed

            async def recover() -> object:
                async with sessions() as session:
                    count = await JobRepository(session).recover_stale(
                        stale_after_seconds=300
                    )
                    await session.commit()
                    return count

            outcomes = await race(heartbeat, recover)
            assert outcomes[0] in {True, False}
            assert isinstance(outcomes[1], int)
            assert outcomes[1] >= (0 if outcomes[0] else 1)
            async with sessions() as session:
                current = await session.get(Job, job.id)
                attempt_row = await session.scalar(
                    select(JobAttempt).where(
                        JobAttempt.job_id == job.id,
                        JobAttempt.attempt_number == attempt,
                    )
                )
                assert current is not None
                assert attempt_row is not None
                if outcomes[0]:
                    assert current.status == JobStatus.RUNNING.value
                    assert current.lease_token == lease_token
                    assert attempt_row.status == JobStatus.RUNNING.value
                else:
                    assert current.status == JobStatus.RETRYING.value
                    assert current.lease_token is None
                    assert attempt_row.status == JobStatus.RETRYING.value

            queue = f"recovery-completion-{iteration}-{uuid.uuid4().hex}"
            job = await enqueue(sessions, queue=queue)
            lease_token, attempt = await claim(sessions, job, "completion-worker")
            await mark_stale(sessions, job.id)

            async def complete() -> object:
                async with sessions() as session:
                    repository = JobRepository(session)
                    current = await repository.get_for_update(job.id)
                    assert current is not None
                    await repository.mark_succeeded(
                        current,
                        {"iteration": iteration},
                        worker_id="completion-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                    await session.commit()
                    return "completed"

            outcomes = await race(complete, recover)
            assert sum(not isinstance(item, Exception) for item in outcomes) >= 1
            async with sessions() as session:
                current = await session.get(Job, job.id)
                assert current is not None
                assert current.status in {
                    JobStatus.SUCCEEDED.value,
                    JobStatus.RETRYING.value,
                }
                if current.status == JobStatus.SUCCEEDED.value:
                    assert current.result == {"iteration": iteration}
                else:
                    assert current.result is None
                assert current.lease_token is None
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancellation_completion_retry_and_late_worker_matrix() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            queue = f"cancel-complete-{iteration}-{uuid.uuid4().hex}"
            job = await enqueue(sessions, queue=queue)
            lease_token, attempt = await claim(sessions, job, "cancel-worker")

            async def cancel() -> object:
                async with sessions() as session:
                    return await JobService(session).cancel(job.id)

            async def complete() -> object:
                async with sessions() as session:
                    repository = JobRepository(session)
                    current = await repository.get_for_update(job.id)
                    assert current is not None
                    await repository.mark_succeeded(
                        current,
                        {"winner": "completion"},
                        worker_id="cancel-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                    await session.commit()
                    return current

            outcomes = await race(cancel, complete)
            assert sum(isinstance(item, Job) for item in outcomes) == 1
            assert sum(isinstance(item, Exception) for item in outcomes) == 1
            async with sessions() as session:
                current = await session.get(Job, job.id)
                attempt_row = await session.scalar(
                    select(JobAttempt).where(
                        JobAttempt.job_id == job.id,
                        JobAttempt.attempt_number == attempt,
                    )
                )
                assert current is not None
                assert attempt_row is not None
                assert current.status in {
                    JobStatus.CANCELLED.value,
                    JobStatus.SUCCEEDED.value,
                }
                assert attempt_row.status == current.status
                assert current.lease_token is None

            queue = f"retry-late-{iteration}-{uuid.uuid4().hex}"
            job = await enqueue(sessions, queue=queue, max_attempts=1)
            lease_token, attempt = await claim(sessions, job, "late-worker")
            async with sessions() as session:
                repository = JobRepository(session)
                current = await repository.get_for_update(job.id)
                assert current is not None
                await repository.mark_failed(
                    current,
                    error_code="TEMPORARY",
                    error_message="injected retryable failure",
                    worker_id="late-worker",
                    lease_token=lease_token,
                    attempt=attempt,
                    retryable=True,
                )
                await session.commit()
                assert current.status == JobStatus.DEAD_LETTER.value

            async def retry() -> object:
                async with sessions() as session:
                    return await JobService(session).retry(job.id)

            async def late_success() -> object:
                async with sessions() as session:
                    repository = JobRepository(session)
                    current = await repository.get_for_update(job.id)
                    assert current is not None
                    await repository.mark_succeeded(
                        current,
                        {"stale": True},
                        worker_id="late-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                    await session.commit()
                    return current

            outcomes = await race(retry, late_success)
            assert sum(isinstance(item, Job) for item in outcomes) == 1
            assert sum(isinstance(item, Exception) for item in outcomes) == 1
            async with sessions() as session:
                current = await session.get(Job, job.id)
                assert current is not None
                assert current.status == JobStatus.RETRYING.value
                assert current.max_attempts == 2
                assert current.result is None

                repository = JobRepository(session)
                locked = await repository.get_for_update(job.id)
                assert locked is not None
                with pytest.raises(JobLeaseLostError):
                    await repository.mark_failed(
                        locked,
                        error_code="STALE",
                        error_message="late failure",
                        worker_id="late-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                await session.rollback()
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_job_listing_remains_consistent_during_transition() -> None:
    engine, sessions = session_factory()
    try:
        for iteration in range(10):
            queue = f"list-transition-{iteration}-{uuid.uuid4().hex}"
            job = await enqueue(sessions, queue=queue)
            lease_token, attempt = await claim(sessions, job, "listing-worker")

            async def complete() -> object:
                async with sessions() as session:
                    repository = JobRepository(session)
                    current = await repository.get_for_update(job.id)
                    assert current is not None
                    await repository.mark_succeeded(
                        current,
                        {"listed": True},
                        worker_id="listing-worker",
                        lease_token=lease_token,
                        attempt=attempt,
                    )
                    await session.commit()
                    return current

            async def list_jobs() -> object:
                async with sessions() as session:
                    rows, total = await JobService(session).list(
                        status=None,
                        queue=queue,
                        limit=10,
                        offset=0,
                    )
                    return rows, total

            completed, listed = await race(complete, list_jobs)
            assert isinstance(completed, Job)
            assert isinstance(listed, tuple)
            rows, total = listed
            assert total == 1
            assert len(rows) == 1
            assert rows[0].id == job.id
            assert rows[0].status in {
                JobStatus.RUNNING.value,
                JobStatus.SUCCEEDED.value,
            }
            async with sessions() as session:
                current = await session.get(Job, job.id)
                assert current is not None
                assert current.status == JobStatus.SUCCEEDED.value
                assert current.result == {"listed": True}
                assert await session.scalar(select(1)) == 1
    finally:
        await engine.dispose()
