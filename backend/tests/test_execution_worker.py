from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.execution import worker
from app.modules.execution.enums import JobStatus
from app.modules.execution.models import Job
from app.modules.execution.protocols import (
    JobCancellationRequested,
    JobExecutionContext,
    RetryableJobError,
)
from app.modules.execution.repository import JobLeaseLostError


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        return None


def make_running_job() -> Job:
    return Job(
        id=uuid.uuid4(),
        job_type="worker.test",
        queue="default",
        priority=100,
        status=JobStatus.RUNNING.value,
        payload={"value": 1},
        attempt=1,
        max_attempts=3,
        available_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        locked_at=datetime.now(UTC),
        locked_by=worker.WORKER_ID,
        lease_token=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        idempotency_key=f"worker-{uuid.uuid4().hex}",
        version=2,
    )


def install_session_and_repository(
    monkeypatch: pytest.MonkeyPatch,
    repository: MagicMock,
) -> FakeSession:
    session = FakeSession()
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(worker, "JobRepository", lambda _session: repository)
    return session


@pytest.mark.asyncio
async def test_heartbeat_refreshes_then_rejects_lost_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MagicMock()
    repository.heartbeat = AsyncMock(side_effect=[True, False])
    session = install_session_and_repository(monkeypatch, repository)
    monkeypatch.setattr(worker.asyncio, "sleep", AsyncMock())

    with pytest.raises(JobLeaseLostError, match="rejected"):
        await worker.heartbeat_lease(uuid.uuid4(), uuid.uuid4(), 1)

    assert repository.heartbeat.await_count == 2
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_heartbeat_database_failure_is_treated_as_lease_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MagicMock()
    repository.heartbeat = AsyncMock(side_effect=RuntimeError("database down"))
    install_session_and_repository(monkeypatch, repository)
    monkeypatch.setattr(worker.asyncio, "sleep", AsyncMock())

    with pytest.raises(JobLeaseLostError, match="finalization is no longer safe"):
        await worker.heartbeat_lease(uuid.uuid4(), uuid.uuid4(), 1)


@pytest.mark.asyncio
async def test_complete_job_commits_only_after_fenced_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = make_running_job()
    repository = MagicMock()
    repository.get_for_update = AsyncMock(return_value=job)
    repository.mark_succeeded = AsyncMock()
    session = install_session_and_repository(monkeypatch, repository)
    assert job.lease_token is not None

    await worker.complete_job(job, {"ok": True}, job.lease_token, job.attempt)

    repository.mark_succeeded.assert_awaited_once()
    session.commit.assert_awaited_once()

    repository.get_for_update.return_value = None
    with pytest.raises(RuntimeError, match="disappeared"):
        await worker.complete_job(job, {}, job.lease_token, job.attempt)


@pytest.mark.asyncio
async def test_fail_job_handles_missing_and_lost_jobs_without_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = make_running_job()
    assert job.lease_token is not None
    repository = MagicMock()
    repository.get_for_update = AsyncMock(return_value=None)
    repository.mark_failed = AsyncMock()
    session = install_session_and_repository(monkeypatch, repository)

    await worker.fail_job(
        job,
        RuntimeError("failure"),
        job.lease_token,
        job.attempt,
        retryable=True,
    )
    session.commit.assert_not_awaited()

    repository.get_for_update.return_value = job
    repository.mark_failed.side_effect = JobLeaseLostError("replaced")
    await worker.fail_job(
        job,
        RuntimeError("failure"),
        job.lease_token,
        job.attempt,
        retryable=True,
    )
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()

    repository.mark_failed.side_effect = None
    await worker.fail_job(
        job,
        RuntimeError("permanent"),
        job.lease_token,
        job.attempt,
        retryable=False,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_owned_job_is_fenced_and_transactional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = make_running_job()
    assert job.lease_token is not None
    repository = MagicMock()
    repository.get_for_update = AsyncMock(return_value=None)
    repository.require_lease = MagicMock()
    repository.cancel = AsyncMock()
    session = install_session_and_repository(monkeypatch, repository)

    await worker.cancel_owned_job(job, job.lease_token, job.attempt)
    repository.cancel.assert_not_awaited()

    repository.get_for_update.return_value = job
    repository.require_lease.side_effect = JobLeaseLostError("replaced")
    await worker.cancel_owned_job(job, job.lease_token, job.attempt)
    session.rollback.assert_awaited_once()

    repository.require_lease.side_effect = None
    await worker.cancel_owned_job(job, job.lease_token, job.attempt)
    repository.cancel.assert_awaited_once_with(job)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_with_lease_returns_handler_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = JobExecutionContext(
        job_id=uuid.uuid4(),
        attempt=1,
        worker_id="worker-1",
        lease_token=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        logical_idempotency_key="logical-job",
        timeout_seconds=1,
    )

    async def handler(
        _context: JobExecutionContext,
        _payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {"ok": True}

    async def heartbeat(
        _job_id: uuid.UUID,
        _lease_token: uuid.UUID,
        _attempt: int,
    ) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(worker, "heartbeat_lease", heartbeat)

    assert await worker.execute_with_lease(handler, context, {}) == {"ok": True}


@pytest.mark.asyncio
async def test_process_once_returns_false_when_queue_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MagicMock()
    repository.recover_stale = AsyncMock(return_value=0)
    repository.claim_next = AsyncMock(return_value=None)
    session = install_session_and_repository(monkeypatch, repository)

    assert await worker.process_once() is False
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_once_rejects_claim_without_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = make_running_job()
    job.lease_token = None
    repository = MagicMock()
    repository.recover_stale = AsyncMock(return_value=0)
    repository.claim_next = AsyncMock(return_value=job)
    install_session_and_repository(monkeypatch, repository)

    with pytest.raises(RuntimeError, match="no lease token"):
        await worker.process_once()


@pytest.mark.asyncio
async def test_process_once_completes_successful_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = make_running_job()
    repository = MagicMock()
    repository.recover_stale = AsyncMock(return_value=0)
    repository.claim_next = AsyncMock(return_value=job)
    install_session_and_repository(monkeypatch, repository)

    async def handler(
        _context: JobExecutionContext,
        _payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setattr(worker, "HANDLERS", {job.job_type: handler})
    execute = AsyncMock(return_value={"ok": True})
    complete = AsyncMock()
    monkeypatch.setattr(worker, "execute_with_lease", execute)
    monkeypatch.setattr(worker, "complete_job", complete)

    assert await worker.process_once() is True
    complete.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "retryable", "cancelled", "lease_lost"),
    [
        (None, False, False, False),
        (RetryableJobError("temporary"), True, False, False),
        (RuntimeError("unknown"), True, False, False),
        (JobCancellationRequested("cancel"), False, True, False),
        (JobLeaseLostError("lost"), False, False, True),
    ],
)
async def test_process_once_classifies_handler_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception | None,
    retryable: bool,
    cancelled: bool,
    lease_lost: bool,
) -> None:
    job = make_running_job()
    repository = MagicMock()
    repository.recover_stale = AsyncMock(return_value=0)
    repository.claim_next = AsyncMock(return_value=job)
    install_session_and_repository(monkeypatch, repository)
    execute = AsyncMock()
    if failure is not None:
        execute.side_effect = failure
    monkeypatch.setattr(worker, "execute_with_lease", execute)
    monkeypatch.setattr(
        worker, "HANDLERS", {} if failure is None else {job.job_type: MagicMock()}
    )
    fail = AsyncMock()
    cancel = AsyncMock()
    complete = AsyncMock()
    monkeypatch.setattr(worker, "fail_job", fail)
    monkeypatch.setattr(worker, "cancel_owned_job", cancel)
    monkeypatch.setattr(worker, "complete_job", complete)

    assert await worker.process_once() is True
    if cancelled:
        cancel.assert_awaited_once()
    elif lease_lost:
        fail.assert_not_awaited()
        complete.assert_not_awaited()
    else:
        fail.assert_awaited_once()
        assert fail.await_args.kwargs["retryable"] is retryable


@pytest.mark.asyncio
async def test_worker_run_polls_after_empty_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = AsyncMock(side_effect=[False, asyncio.CancelledError()])
    sleep = AsyncMock()
    monkeypatch.setattr(worker, "process_once", process)
    monkeypatch.setattr(worker.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.run()
    sleep.assert_awaited_once_with(worker.POLL_SECONDS)
