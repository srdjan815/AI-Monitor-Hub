from __future__ import annotations

import asyncio
import logging
import os
import socket

from app.db.session import AsyncSessionLocal
from app.modules.execution.handlers import HANDLERS
from app.modules.execution.repository import JobRepository

logger = logging.getLogger(__name__)

QUEUE = os.getenv("WORKER_QUEUE", "default")
POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "1"))
STALE_AFTER_SECONDS = int(os.getenv("WORKER_STALE_AFTER_SECONDS", "300"))
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}:{os.getpid()}")


async def process_once() -> bool:
    async with AsyncSessionLocal() as session:
        repository = JobRepository(session)
        await repository.recover_stale(stale_after_seconds=STALE_AFTER_SECONDS)
        job = await repository.claim_next(queue=QUEUE, worker_id=WORKER_ID)
        await session.commit()

    if job is None:
        return False

    handler = HANDLERS.get(job.job_type)
    try:
        if handler is None:
            raise LookupError(f"No handler registered for {job.job_type}")
        result = await handler(job.payload)
        async with AsyncSessionLocal() as session:
            repository = JobRepository(session)
            current = await repository.get(job.id)
            if current is None:
                raise RuntimeError("Claimed job disappeared")
            await repository.mark_succeeded(current, result)
            await session.commit()
    except Exception as exc:
        logger.exception("Job %s failed", job.id)
        async with AsyncSessionLocal() as session:
            repository = JobRepository(session)
            current = await repository.get(job.id)
            if current is not None:
                await repository.mark_failed(
                    current,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
                await session.commit()
    return True


async def run() -> None:
    logger.info("Worker started: id=%s queue=%s", WORKER_ID, QUEUE)
    while True:
        processed = await process_once()
        if not processed:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
