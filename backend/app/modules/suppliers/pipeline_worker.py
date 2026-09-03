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
from app.modules.suppliers.pipeline_recovery_service import (
    SupplierPipelineRecoveryService,
)


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
    try:
        async with AsyncSessionLocal() as session:
            result = await SupplierPipelineOrchestrator(session).execute(
                source_id,
                run_id,
            )
    except Exception as exc:
        async with AsyncSessionLocal() as recovery_session:
            await SupplierPipelineRecoveryService(recovery_session).fail_if_active(
                source_id,
                run_id,
                code="pipeline_worker_execution_failed",
                message=(
                    "Worker nije završio obradu cenovnika. Pipeline je bezbedno "
                    "zatvoren; proverite Incident centar pre ponovnog pokretanja."
                ),
            )
        raise exc
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
