from __future__ import annotations

from datetime import UTC, datetime

from app.modules.suppliers.pipeline_contracts import PipelinePhaseResult


def failed_phase_results(
    current: dict[str, object], phase: str, error_code: str
) -> dict[str, object]:
    now = datetime.now(UTC)
    result = PipelinePhaseResult(
        status="FAILED",
        started_at=now,
        completed_at=now,
        duration_ms=0,
        error_code=error_code,
        warning_count=0,
        error_count=1,
    )
    return {**current, phase: result.as_dict()}


__all__ = ["failed_phase_results"]
