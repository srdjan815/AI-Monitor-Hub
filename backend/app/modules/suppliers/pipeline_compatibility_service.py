from __future__ import annotations

from app.modules.suppliers.pipeline_contracts import PipelineContext
from app.modules.suppliers.pipeline_models import SupplierSchemaCompatibilityReport
from app.modules.suppliers.pipeline_repository import SupplierPipelineRepository
from app.modules.suppliers.schema_compatibility_service import CompatibilityResult
from app.modules.suppliers.schema_profile_models import SupplierSchemaProfile


class SupplierPipelineCompatibilityService:
    """Idempotent persistence for the single compatibility report of a run."""

    def __init__(self, repository: SupplierPipelineRepository) -> None:
        self.repository = repository

    async def upsert(
        self,
        context: PipelineContext,
        analyzed: SupplierSchemaProfile,
        result: CompatibilityResult,
    ) -> SupplierSchemaCompatibilityReport:
        assert context.active_schema is not None
        assert context.artifact is not None
        values: dict[str, object] = {
            "artifact_id": context.artifact.id,
            "active_schema_profile_id": context.active_schema.id,
            "analyzed_schema_profile_id": analyzed.id,
            "result": result.status,
            "severity": result.severity,
            "changes": [
                {
                    "code": change.code,
                    "path": change.path,
                    "classification": change.classification,
                    "severity": change.severity,
                    "expected": change.expected,
                    "actual": change.actual,
                    "message": change.message,
                }
                for change in result.changes
            ],
            "summary": result.summary,
        }
        report = await self.repository.compatibility_report(context.run.id)
        if report is None:
            report = SupplierSchemaCompatibilityReport(
                pipeline_run_id=context.run.id,
                **values,
            )
            await self.repository.add(report)
        else:
            values["version"] = report.version + 1
            await self.repository.mutate(report, values)
        return report


__all__ = ["SupplierPipelineCompatibilityService"]
