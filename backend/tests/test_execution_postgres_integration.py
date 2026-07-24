from __future__ import annotations

import asyncio
import os
import uuid
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


@pytest.mark.asyncio
async def test_concurrent_idempotent_enqueue_returns_canonical_job() -> None:
    engine = create_async_engine(DATABASE_URL, pool_size=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    key = f"execution-audit-{uuid.uuid4().hex}"
    payload = JobCreate(job_type="forensic.noop", idempotency_key=key)

    async def enqueue() -> Job:
        async with sessions() as session:
            return await JobService(session).enqueue(payload)

    try:
        first, second = await asyncio.gather(enqueue(), enqueue())
        assert first.id == second.id

        async with sessions() as session:
            count = await session.scalar(
                select(func.count()).select_from(Job).where(Job.idempotency_key == key)
            )
        assert count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelling_running_job_fences_worker_and_finishes_attempt() -> None:
    engine = create_async_engine(DATABASE_URL, pool_size=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queue = f"cancel-{uuid.uuid4().hex}"
    try:
        async with sessions() as session:
            job = await JobService(session).enqueue(
                JobCreate(job_type="forensic.noop", queue=queue)
            )

        async with sessions() as session:
            repository = JobRepository(session)
            claimed = await repository.claim_next(
                queue=queue,
                worker_id="worker-cancelled",
            )
            assert claimed is not None
            assert claimed.lease_token is not None
            lease_token = claimed.lease_token
            attempt = claimed.attempt
            await session.commit()

        async with sessions() as session:
            cancelled = await JobService(session).cancel(job.id)
            assert cancelled.status == JobStatus.CANCELLED.value
            assert cancelled.finished_at is not None
            assert cancelled.lease_token is None

        async with sessions() as session:
            repository = JobRepository(session)
            stale = await repository.get_for_update(job.id)
            assert stale is not None
            with pytest.raises(JobLeaseLostError):
                await repository.mark_succeeded(
                    stale,
                    {"external_effect": "must-not-finalize"},
                    worker_id="worker-cancelled",
                    lease_token=lease_token,
                    attempt=attempt,
                )
            await session.rollback()

        async with sessions() as session:
            attempt_row = await session.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt_number == attempt,
                )
            )
            assert attempt_row is not None
            assert attempt_row.status == JobStatus.CANCELLED.value
            assert attempt_row.finished_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_retryable_failure_dead_letters_then_manual_retry_requeues() -> None:
    engine = create_async_engine(DATABASE_URL, pool_size=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queue = f"dead-letter-{uuid.uuid4().hex}"
    try:
        async with sessions() as session:
            job = await JobService(session).enqueue(
                JobCreate(
                    job_type="forensic.noop",
                    queue=queue,
                    max_attempts=1,
                )
            )

        async with sessions() as session:
            repository = JobRepository(session)
            claimed = await repository.claim_next(
                queue=queue,
                worker_id="worker-dead-letter",
            )
            assert claimed is not None
            assert claimed.lease_token is not None
            await repository.mark_failed(
                claimed,
                error_code="TEMPORARY",
                error_message="dependency unavailable",
                worker_id="worker-dead-letter",
                lease_token=claimed.lease_token,
                attempt=claimed.attempt,
                retryable=True,
            )
            await session.commit()
            assert claimed.status == JobStatus.DEAD_LETTER.value

        async with sessions() as session:
            retried = await JobService(session).retry(job.id)
            assert retried.status == JobStatus.RETRYING.value
            assert retried.max_attempts == 2
            assert retried.error_code is None

        async with sessions() as session:
            claimed_again = await JobRepository(session).claim_next(
                queue=queue,
                worker_id="worker-retry",
            )
            assert claimed_again is not None
            assert claimed_again.id == job.id
            assert claimed_again.attempt == 2
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_claim_respects_priority_and_future_schedule() -> None:
    engine = create_async_engine(DATABASE_URL, pool_size=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queue = f"priority-{uuid.uuid4().hex}"
    try:
        async with sessions() as session:
            low_priority = await JobService(session).enqueue(
                JobCreate(
                    job_type="forensic.noop",
                    queue=queue,
                    priority=100,
                )
            )
        async with sessions() as session:
            high_priority = await JobService(session).enqueue(
                JobCreate(
                    job_type="forensic.noop",
                    queue=queue,
                    priority=10,
                )
            )
        async with sessions() as session:
            await JobService(session).enqueue(
                JobCreate(
                    job_type="forensic.noop",
                    queue=queue,
                    priority=0,
                    available_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )

        async with sessions() as session:
            claimed = await JobRepository(session).claim_next(
                queue=queue,
                worker_id="worker-priority",
            )
            assert claimed is not None
            assert claimed.id == high_priority.id
            assert claimed.id != low_priority.id
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_worker_cannot_finalize_recovered_job() -> None:
    engine = create_async_engine(DATABASE_URL, pool_size=4)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    key = f"lease-audit-{uuid.uuid4().hex}"
    queue = f"lease-{uuid.uuid4().hex}"
    try:
        async with sessions() as session:
            job = await JobService(session).enqueue(
                JobCreate(
                    job_type="forensic.noop",
                    idempotency_key=key,
                    queue=queue,
                )
            )

        async with sessions() as session:
            repository = JobRepository(session)
            claimed = await repository.claim_next(
                queue=queue, worker_id="worker-original"
            )
            assert claimed is not None
            assert claimed.id == job.id
            assert claimed.lease_token is not None
            lease_token = claimed.lease_token
            attempt = claimed.attempt
            claimed.locked_at = datetime.now(UTC) - timedelta(seconds=600)
            await session.commit()

        async with sessions() as session:
            recovered = await JobRepository(session).recover_stale(
                stale_after_seconds=300
            )
            await session.commit()
        assert recovered >= 1

        async with sessions() as session:
            repository = JobRepository(session)
            stale_view = await repository.get_for_update(job.id)
            assert stale_view is not None
            with pytest.raises(JobLeaseLostError):
                await repository.mark_succeeded(
                    stale_view,
                    {"incorrect": True},
                    worker_id="worker-original",
                    lease_token=lease_token,
                    attempt=attempt,
                )
            await session.rollback()

        async with sessions() as session:
            current = await JobRepository(session).get(job.id)
            assert current is not None
            assert current.status == JobStatus.RETRYING.value
            assert current.lease_token is None
            assert current.result is None
    finally:
        await engine.dispose()
