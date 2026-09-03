from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, TypeAlias


class JobExecutionError(RuntimeError):
    """Base class for errors with an explicit execution policy."""


class RetryableJobError(JobExecutionError):
    """A handler failure that may succeed on a later bounded attempt."""


class PermanentJobError(JobExecutionError):
    """A handler failure that must not be retried automatically."""


class HandlerTimeoutError(RetryableJobError):
    """The handler exceeded the configured worker timeout."""


class JobCancellationRequested(JobExecutionError):
    """Cooperative cancellation was observed by a handler."""


@dataclass(slots=True)
class JobExecutionContext:
    """Attempt-scoped metadata passed to every execution handler."""

    job_id: uuid.UUID
    attempt: int
    worker_id: str
    lease_token: uuid.UUID
    correlation_id: uuid.UUID
    logical_idempotency_key: str
    timeout_seconds: float
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def attempt_id(self) -> str:
        """Stable identity for this database job attempt."""

        return f"{self.job_id}:{self.attempt}"

    def side_effect_key(self, operation: str) -> str:
        """Build a stable cross-attempt key for one external side effect."""

        normalized = operation.strip()
        if not normalized:
            raise ValueError("operation must not be empty")
        return f"{self.logical_idempotency_key}:{normalized}"

    async def checkpoint(self) -> None:
        """Yield control and fail promptly after cooperative cancellation."""

        await asyncio.sleep(0)
        if self.cancel_event.is_set():
            raise JobCancellationRequested("Job cancellation requested")


@dataclass(frozen=True, slots=True)
class JobResult:
    """Structured handler result persisted by the worker."""

    data: dict[str, Any]


class JobHandler(Protocol):
    def __call__(
        self,
        context: JobExecutionContext,
        payload: dict[str, Any],
    ) -> Awaitable[JobResult | dict[str, Any]]: ...


HandlerRegistry: TypeAlias = dict[str, JobHandler]
HandlerCallable: TypeAlias = Callable[
    [JobExecutionContext, dict[str, Any]],
    Awaitable[JobResult | dict[str, Any]],
]
