from __future__ import annotations

import uuid
from typing import Any

from app.db.session import AsyncSessionLocal
from app.modules.execution.protocols import (
    JobExecutionContext,
    JobResult,
    PermanentJobError,
)
from app.modules.suppliers.pipeline_service import SupplierPipelineOrchestrator


async def supplier_pipeline_handler(
    context: JobExecutionContext,
    payload: dict[str, Any],
) -> JobResult:
    await context.checkpoint()
    try:
        source_id = uuid.UUID(str(payload["source_id"]))
        run_id = uuid.UUID(str(payload["pipeline_run_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise PermanentJobError("Supplier Pipeline job payload is invalid") from exc
    async with AsyncSessionLocal() as session:
        result = await SupplierPipelineOrchestrator(session).execute(
            source_id,
            run_id,
        )
    await context.checkpoint()
    return JobResult(
        data={
            "pipeline_run_id": str(run_id),
            "status": result.status,
            "completed_phase": result.completed_phase,
            "warnings": result.warnings,
            "errors": result.errors,
            "telemetry": result.telemetry,
        }
    )


__all__ = ["supplier_pipeline_handler"]
