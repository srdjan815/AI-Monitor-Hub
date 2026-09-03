from __future__ import annotations

import asyncio
import inspect
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.execution.enums import JobStatus
from app.modules.execution.handlers import HANDLERS, health_echo, synthetic
from app.modules.execution.models import Job
from app.modules.execution.protocols import (
    HandlerTimeoutError,
    JobCancellationRequested,
    JobExecutionContext,
    JobResult,
    PermanentJobError,
    RetryableJobError,
)
from app.modules.execution.repository import (
    InvalidJobTransitionError,
    JobIdempotencyConflictError,
    JobLeaseLostError,
    JobRepository,
    retry_delay_seconds,
)
from app.modules.execution.schemas import JobCreate
from app.modules.execution.service import JobService
from app.modules.execution import worker


def test_job_create_defaults() -> None:
    job = JobCreate(job_type="system.health_echo")
    assert job.queue == "default"
    assert job.priority == 100
    assert job.max_attempts == 3
    assert job.payload == {}


def test_job_status_values_are_stable() -> None:
    assert JobStatus.PENDING.value == "PENDING"
    assert JobStatus.FAILED.value == "FAILED"
    assert JobStatus.CANCELLED.value == "CANCELLED"
    assert JobStatus.DEAD_LETTER.value == "DEAD_LETTER"


def test_registered_handlers_accept_attempt_context_and_payload() -> None:
    for job_type, handler in HANDLERS.items():
        parameters = list(inspect.signature(handler).parameters)
        assert parameters == ["context", "payload"], job_type


def _job(
    *,
    status: JobStatus = JobStatus.RUNNING,
    attempt: int = 1,
    max_attempts: int = 3,
) -> Job:
    lease_token = uuid.uuid4() if status == JobStatus.RUNNING else None
    return Job(
        id=uuid.uuid4(),
        job_type="system.health_echo",
        queue="default",
        priority=100,
        status=status.value,
        payload={},
        attempt=attempt,
        max_attempts=max_attempts,
        available_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        locked_at=datetime.now(UTC) if lease_token else None,
        locked_by="worker-1" if lease_token else None,
        lease_token=lease_token,
        correlation_id=uuid.uuid4(),
        version=1,
    )


def _context(*, timeout_seconds: float = 1) -> JobExecutionContext:
    job_id = uuid.uuid4()
    return JobExecutionContext(
        job_id=job_id,
        attempt=2,
        worker_id="worker-1",
        lease_token=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        logical_idempotency_key=f"job:{job_id}",
        timeout_seconds=timeout_seconds,
    )


def test_retry_delay_is_deterministic_jittered_and_bounded() -> None:
    job_id = uuid.uuid4()
    first = retry_delay_seconds(job_id, 1)

    assert first == retry_delay_seconds(job_id, 1)
    assert 4 <= first <= 6
    assert retry_delay_seconds(job_id, 100) == 300


@pytest.mark.asyncio
async def test_context_exposes_stable_idempotency_metadata_and_cancellation() -> None:
    context = _context()

    assert context.attempt_id == f"{context.job_id}:2"
    assert context.side_effect_key("publish") == (
        f"{context.logical_idempotency_key}:publish"
    )
    with pytest.raises(ValueError):
        context.side_effect_key(" ")

    context.cancel_event.set()
    with pytest.raises(JobCancellationRequested):
        await context.checkpoint()


@pytest.mark.asyncio
async def test_health_handler_returns_structured_result() -> None:
    context = _context()

    result = await health_echo(context, {"probe": True})

    assert isinstance(result, JobResult)
    assert result.data == {
        "echo": {"probe": True},
        "handled": True,
        "attempt_id": context.attempt_id,
    }


@pytest.mark.asyncio
async def test_synthetic_handler_has_bounded_deterministic_outcomes() -> None:
    context = _context()

    result = await synthetic(context, {"duration_ms": 0})
    assert result.data == {
        "synthetic": True,
        "duration_ms": 0,
        "attempt": context.attempt,
    }

    with pytest.raises(RetryableJobError, match="retryable"):
        await synthetic(
            context,
            {
                "duration_ms": 0,
                "outcome": "retryable",
                "retry_until_attempt": context.attempt,
            },
        )
    with pytest.raises(PermanentJobError, match="permanent"):
        await synthetic(context, {"duration_ms": 0, "outcome": "permanent"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"duration_ms": True},
        {"duration_ms": -1},
        {"duration_ms": 60_001},
        {"outcome": "unknown"},
        {"retry_until_attempt": True},
        {"retry_until_attempt": -1},
    ],
)
async def test_synthetic_handler_rejects_invalid_payload(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(PermanentJobError):
        await synthetic(_context(), payload)


@pytest.mark.asyncio
async def test_repository_classifies_retryable_permanent_and_exhausted_failures() -> (
    None
):
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = JobRepository(session)
    repository._finish_attempt = AsyncMock()  # type: ignore[method-assign]

    retrying = _job(attempt=1, max_attempts=3)
    assert retrying.lease_token is not None
    await repository.mark_failed(
        retrying,
        error_code="TEMPORARY",
        error_message="try again",
        worker_id="worker-1",
        lease_token=retrying.lease_token,
        attempt=1,
        retryable=True,
    )
    assert retrying.status == JobStatus.RETRYING.value
    assert retrying.finished_at is None
    assert retrying.available_at > datetime.now(UTC)

    permanent = _job(attempt=1, max_attempts=3)
    assert permanent.lease_token is not None
    await repository.mark_failed(
        permanent,
        error_code="INVALID_INPUT",
        error_message="do not retry",
        worker_id="worker-1",
        lease_token=permanent.lease_token,
        attempt=1,
        retryable=False,
    )
    assert permanent.status == JobStatus.FAILED.value
    assert permanent.finished_at is not None

    exhausted = _job(attempt=3, max_attempts=3)
    assert exhausted.lease_token is not None
    await repository.mark_failed(
        exhausted,
        error_code="TEMPORARY",
        error_message="still failing",
        worker_id="worker-1",
        lease_token=exhausted.lease_token,
        attempt=3,
        retryable=True,
    )
    assert exhausted.status == JobStatus.DEAD_LETTER.value
    assert exhausted.finished_at is not None


@pytest.mark.asyncio
async def test_repository_cancel_is_idempotent_and_fences_running_attempt() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = JobRepository(session)
    repository._finish_attempt = AsyncMock()  # type: ignore[method-assign]
    job = _job()

    assert await repository.cancel(job) is True
    assert job.status == JobStatus.CANCELLED.value
    assert job.lease_token is None
    assert job.locked_by is None
    assert job.finished_at is not None
    assert await repository.cancel(job) is False

    completed = _job(status=JobStatus.SUCCEEDED)
    with pytest.raises(InvalidJobTransitionError):
        await repository.cancel(completed)


@pytest.mark.asyncio
async def test_repository_manual_retry_guarantees_one_new_attempt() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = JobRepository(session)
    job = _job(
        status=JobStatus.DEAD_LETTER,
        attempt=3,
        max_attempts=3,
    )
    job.error_code = "EXHAUSTED"
    job.finished_at = datetime.now(UTC)

    await repository.retry(job)

    assert job.status == JobStatus.RETRYING.value
    assert job.max_attempts == 4
    assert job.error_code is None
    assert job.finished_at is None

    retryable_failure = _job(
        status=JobStatus.FAILED,
        attempt=1,
        max_attempts=3,
    )
    await repository.retry(retryable_failure)
    assert retryable_failure.status == JobStatus.RETRYING.value
    assert retryable_failure.max_attempts == 3

    with pytest.raises(InvalidJobTransitionError):
        await repository.retry(_job(status=JobStatus.PENDING))


@pytest.mark.asyncio
async def test_invoke_handler_supports_structured_and_legacy_dict_results() -> None:
    context = _context()

    async def structured(
        execution: JobExecutionContext,
        payload: dict[str, object],
    ) -> JobResult:
        assert execution is context
        return JobResult(data={"value": payload["value"]})

    async def dictionary(
        execution: JobExecutionContext,
        payload: dict[str, object],
    ) -> dict[str, object]:
        assert execution is context
        return {"value": payload["value"]}

    assert await worker.invoke_handler(structured, context, {"value": 7}) == {
        "value": 7
    }
    assert await worker.invoke_handler(dictionary, context, {"value": 8}) == {
        "value": 8
    }


@pytest.mark.asyncio
async def test_invoke_handler_rejects_invalid_result_and_enforces_timeout() -> None:
    context = _context(timeout_seconds=0.01)

    async def invalid(
        _execution: JobExecutionContext,
        _payload: dict[str, object],
    ) -> object:
        return object()

    async def slow(
        _execution: JobExecutionContext,
        _payload: dict[str, object],
    ) -> dict[str, object]:
        await asyncio.sleep(1)
        return {}

    with pytest.raises(PermanentJobError):
        await worker.invoke_handler(invalid, context, {})
    with pytest.raises(HandlerTimeoutError):
        await worker.invoke_handler(slow, context, {})


@pytest.mark.asyncio
async def test_execute_with_lease_cancels_handler_when_heartbeat_loses_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def long_handler(
        _execution: JobExecutionContext,
        _payload: dict[str, object],
    ) -> dict[str, object]:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def lose_lease(
        _job_id: uuid.UUID,
        _lease_token: uuid.UUID,
        _attempt: int,
    ) -> None:
        await started.wait()
        raise JobLeaseLostError("lease replaced")

    monkeypatch.setattr(worker, "heartbeat_lease", lose_lease)

    with pytest.raises(JobLeaseLostError):
        await worker.execute_with_lease(long_handler, _context(), {})
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_enqueue_service_commits_success_and_rolls_back_conflict() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    service = JobService(session)
    repository = MagicMock()
    repository.create = AsyncMock()
    service.repository = repository
    data = JobCreate(job_type="system.health_echo")
    job = _job(status=JobStatus.PENDING, attempt=0)
    repository.create.return_value = job

    assert await service.enqueue(data) is job
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(job)

    repository.create.side_effect = JobIdempotencyConflictError("different")
    with pytest.raises(HTTPException) as conflict:
        await service.enqueue(data)
    assert conflict.value.status_code == 409
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_integrity_race_returns_matching_canonical_job() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    service = JobService(session)
    repository = MagicMock()
    service.repository = repository
    data = JobCreate(
        job_type="system.health_echo",
        idempotency_key="same-request",
    )
    existing = _job(status=JobStatus.PENDING, attempt=0)
    existing.idempotency_key = data.idempotency_key
    repository.create = AsyncMock(
        side_effect=IntegrityError("insert", {}, RuntimeError("unique"))
    )
    repository.get_by_idempotency_key = AsyncMock(return_value=existing)
    repository.require_same_idempotent_request = MagicMock()

    assert await service.enqueue(data) is existing
    session.rollback.assert_awaited_once()
    repository.require_same_idempotent_request.assert_called_once_with(
        existing,
        data,
    )
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_management_service_rolls_back_not_found_and_conflict() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    service = JobService(session)
    repository = MagicMock()
    repository.get_for_update = AsyncMock(return_value=None)
    repository.cancel = AsyncMock()
    repository.retry = AsyncMock()
    service.repository = repository

    with pytest.raises(HTTPException) as missing:
        await service.cancel(uuid.uuid4())
    assert missing.value.status_code == 404

    repository.get_for_update.return_value = _job(status=JobStatus.SUCCEEDED)
    repository.retry.side_effect = InvalidJobTransitionError("cannot retry")
    with pytest.raises(HTTPException) as conflict:
        await service.retry(uuid.uuid4())
    assert conflict.value.status_code == 409
    assert session.rollback.await_count == 2
    session.commit.assert_not_awaited()
