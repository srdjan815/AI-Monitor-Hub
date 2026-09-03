from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from typing import Any

from app.db.session import AsyncSessionLocal
from app.modules.execution.handlers import HANDLERS
from app.modules.execution.models import Job
from app.modules.execution.protocols import (
    HandlerTimeoutError,
    JobCancellationRequested,
    JobExecutionContext,
    JobHandler,
    JobResult,
    PermanentJobError,
    RetryableJobError,
)
from app.modules.execution.repository import JobLeaseLostError, JobRepository
from app.modules.suppliers.pipeline_scheduler import SupplierPipelineScheduler

logger = logging.getLogger(__name__)

QUEUE = os.getenv("WORKER_QUEUE", "default")
POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "1"))
STALE_AFTER_SECONDS = int(os.getenv("WORKER_STALE_AFTER_SECONDS", "300"))
HEARTBEAT_SECONDS = float(
    os.getenv(
        "WORKER_HEARTBEAT_SECONDS",
        str(min(5.0, max(1.0, STALE_AFTER_SECONDS / 3))),
    )
)
HANDLER_TIMEOUT_SECONDS = float(os.getenv("WORKER_HANDLER_TIMEOUT_SECONDS", "300"))
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}:{os.getpid()}")


async def heartbeat_lease(
    job_id: uuid.UUID,
    lease_token: uuid.UUID,
    attempt: int,
) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with AsyncSessionLocal() as session:
                owned = await JobRepository(session).heartbeat(
                    job_id=job_id,
                    worker_id=WORKER_ID,
                    lease_token=lease_token,
                    attempt=attempt,
                )
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise JobLeaseLostError(
                "Heartbeat failed; handler finalization is no longer safe"
            ) from exc
        if not owned:
            raise JobLeaseLostError("Heartbeat rejected after lease loss")


async def complete_job(
    job: Job,
    result: dict[str, Any],
    lease_token: uuid.UUID,
    attempt: int,
) -> None:
    async with AsyncSessionLocal() as session:
        repository = JobRepository(session)
        current = await repository.get_for_update(job.id)
        if current is None:
            raise RuntimeError("Claimed job disappeared")
        await repository.mark_succeeded(
            current,
            result,
            worker_id=WORKER_ID,
            lease_token=lease_token,
            attempt=attempt,
        )
        await session.commit()


async def fail_job(
    job: Job,
    exc: Exception,
    lease_token: uuid.UUID,
    attempt: int,
    *,
    retryable: bool,
) -> None:
    async with AsyncSessionLocal() as session:
        repository = JobRepository(session)
        current = await repository.get_for_update(job.id)
        if current is None:
            return
        try:
            await repository.mark_failed(
                current,
                error_code=type(exc).__name__,
                error_message=str(exc),
                worker_id=WORKER_ID,
                lease_token=lease_token,
                attempt=attempt,
                retryable=retryable,
            )
        except JobLeaseLostError:
            await session.rollback()
            logger.warning("Job %s failure ignored after lease loss", job.id)
        else:
            await session.commit()


async def cancel_owned_job(
    job: Job,
    lease_token: uuid.UUID,
    attempt: int,
) -> None:
    async with AsyncSessionLocal() as session:
        repository = JobRepository(session)
        current = await repository.get_for_update(job.id)
        if current is None:
            return
        try:
            repository.require_lease(
                current,
                worker_id=WORKER_ID,
                lease_token=lease_token,
                attempt=attempt,
            )
            await repository.cancel(current)
        except JobLeaseLostError:
            await session.rollback()
            logger.warning("Job %s cancellation ignored after lease loss", job.id)
        else:
            await session.commit()


async def invoke_handler(
    handler: JobHandler,
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with asyncio.timeout(context.timeout_seconds):
            result = await handler(context, payload)
    except TimeoutError as exc:
        raise HandlerTimeoutError(
            f"Handler exceeded {context.timeout_seconds:g} seconds"
        ) from exc

    if isinstance(result, JobResult):
        return result.data
    if not isinstance(result, dict):
        raise PermanentJobError("Handler must return JobResult or a dictionary")
    return result


async def execute_with_lease(
    handler: JobHandler,
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> dict[str, Any]:
    handler_task = asyncio.create_task(invoke_handler(handler, context, payload))
    heartbeat_task = asyncio.create_task(
        heartbeat_lease(
            context.job_id,
            context.lease_token,
            context.attempt,
        )
    )
    try:
        done, _ = await asyncio.wait(
            {handler_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat_task in done:
            context.cancel_event.set()
            handler_task.cancel()
            await asyncio.gather(handler_task, return_exceptions=True)
            heartbeat_task.result()
            raise JobLeaseLostError("Heartbeat stopped unexpectedly")
        return await handler_task
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


async def process_once() -> bool:
    async with AsyncSessionLocal() as session:
        repository = JobRepository(session)
        await repository.recover_stale(stale_after_seconds=STALE_AFTER_SECONDS)
        job = await repository.claim_next(queue=QUEUE, worker_id=WORKER_ID)
        await session.commit()

    if job is None:
        return False
    if job.lease_token is None:
        raise RuntimeError("Claimed job has no lease token")
    lease_token = job.lease_token
    attempt = job.attempt

    handler = HANDLERS.get(job.job_type)
    requested_timeout = job.payload.get("timeout_seconds")
    timeout_seconds = (
        float(requested_timeout)
        if isinstance(requested_timeout, int)
        and not isinstance(requested_timeout, bool)
        and 1 <= requested_timeout <= 86400
        else HANDLER_TIMEOUT_SECONDS
    )
    context = JobExecutionContext(
        job_id=job.id,
        attempt=attempt,
        worker_id=WORKER_ID,
        lease_token=lease_token,
        correlation_id=job.correlation_id,
        logical_idempotency_key=job.idempotency_key or str(job.id),
        timeout_seconds=timeout_seconds,
    )
    try:
        if handler is None:
            raise PermanentJobError(f"No handler registered for {job.job_type}")
        result = await execute_with_lease(handler, context, job.payload)
        await complete_job(job, result, lease_token, attempt)
    except JobLeaseLostError:
        logger.warning("Job %s lease was lost; stale completion ignored", job.id)
    except JobCancellationRequested:
        await cancel_owned_job(job, lease_token, attempt)
    except PermanentJobError as exc:
        logger.error("Job %s failed permanently: %s", job.id, exc)
        await fail_job(
            job,
            exc,
            lease_token,
            attempt,
            retryable=False,
        )
    except RetryableJobError as exc:
        logger.warning("Job %s failed and will be retried: %s", job.id, exc)
        await fail_job(
            job,
            exc,
            lease_token,
            attempt,
            retryable=True,
        )
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        await fail_job(
            job,
            exc,
            lease_token,
            attempt,
            retryable=True,
        )
    return True


async def dispatch_supplier_schedules() -> int:
    async with AsyncSessionLocal() as session:
        return await SupplierPipelineScheduler(session).dispatch_due()


async def run() -> None:
    logger.info("Worker started: id=%s queue=%s", WORKER_ID, QUEUE)
    while True:
        await dispatch_supplier_schedules()
        processed = await process_once()
        if not processed:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
