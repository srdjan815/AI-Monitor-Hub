from __future__ import annotations

import asyncio
from typing import Any

from app.modules.execution.protocols import (
    HandlerRegistry,
    JobExecutionContext,
    JobResult,
    PermanentJobError,
    RetryableJobError,
)
from app.modules.suppliers.pipeline_worker import supplier_pipeline_handler
from app.modules.suppliers.currency_worker import supplier_currency_rate_handler

MAX_SYNTHETIC_DURATION_MS = 60_000


async def health_echo(
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> JobResult:
    await context.checkpoint()
    return JobResult(
        data={
            "echo": payload,
            "handled": True,
            "attempt_id": context.attempt_id,
        }
    )


async def test(
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> JobResult:
    await asyncio.sleep(1)
    await context.checkpoint()
    return JobResult(
        data={
            "success": True,
            "message": payload.get("message"),
            "handled_by": "test_handler",
        }
    )


async def synthetic(
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> JobResult:
    """Run a bounded, side-effect-free workload for operational validation."""

    duration_ms = payload.get("duration_ms", 0)
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)):
        raise PermanentJobError("duration_ms must be a number")
    if not 0 <= duration_ms <= MAX_SYNTHETIC_DURATION_MS:
        raise PermanentJobError(
            f"duration_ms must be between 0 and {MAX_SYNTHETIC_DURATION_MS}"
        )

    outcome = payload.get("outcome", "success")
    if outcome not in {"success", "retryable", "permanent"}:
        raise PermanentJobError("outcome must be success, retryable, or permanent")

    retry_until_attempt = payload.get("retry_until_attempt", 0)
    if isinstance(retry_until_attempt, bool) or not isinstance(
        retry_until_attempt, int
    ):
        raise PermanentJobError("retry_until_attempt must be an integer")
    if retry_until_attempt < 0:
        raise PermanentJobError("retry_until_attempt must not be negative")

    await asyncio.sleep(duration_ms / 1000)
    await context.checkpoint()

    if outcome == "retryable" and context.attempt <= retry_until_attempt:
        raise RetryableJobError("Synthetic retryable failure")
    if outcome == "permanent":
        raise PermanentJobError("Synthetic permanent failure")

    return JobResult(
        data={
            "synthetic": True,
            "duration_ms": duration_ms,
            "attempt": context.attempt,
        }
    )


HANDLERS: HandlerRegistry = {
    "supplier.currency_rate": supplier_currency_rate_handler,
    "supplier.pipeline": supplier_pipeline_handler,
    "system.health_echo": health_echo,
    "system.synthetic": synthetic,
    "test": test,
}
