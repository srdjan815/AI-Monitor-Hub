from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.incident_support import SupplierIncidentSupport
from app.modules.suppliers.pipeline_contracts import PipelineContext


class SupplierPipelineIncidentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.support = SupplierIncidentSupport(session)

    async def record_failure(
        self,
        context: PipelineContext,
        code: str,
        message: str,
    ) -> None:
        incident_types = {
            "pipeline_schema_incompatible": "PIPELINE_SCHEMA_INCOMPATIBLE",
            "pipeline_active_contract_missing": "PIPELINE_CONFIGURATION_MISSING",
            "acquisition_http_failed": "PIPELINE_SOURCE_UNAVAILABLE",
            "pipeline_worker_dead_letter": "PIPELINE_WORKER_FAILED",
            "pipeline_worker_execution_failed": "PIPELINE_WORKER_FAILED",
            "pipeline_worker_terminal_mismatch": "PIPELINE_STATE_RECOVERED",
        }
        incident_type = incident_types.get(code, "PIPELINE_EXECUTION_FAILED")
        severity = "HIGH" if code == "acquisition_http_failed" else "MEDIUM"
        priority = "P2" if severity == "HIGH" else "P3"
        try:
            await self.support.create_or_occurrence(
                incident_id=uuid.uuid4(),
                supplier_id=context.supplier.id,
                source_id=context.source.id,
                source_domain="PIPELINE",
                incident_type=incident_type,
                severity=severity,
                priority=priority,
                title="Automatska obrada cenovnika nije uspela",
                description=message,
                source_entity_id=context.source.id,
                context={
                    "pipeline_run_id": str(context.run.id),
                    "pipeline_code": context.run.pipeline_code,
                    "phase": context.run.current_phase,
                    "failure_code": code,
                    "recommended_action": self._recommended_action(code),
                    "workflow": [
                        "Proverite fazu i razlog incidenta.",
                        "Ispravite konekciju, analizu ili mapiranje prema navedenoj fazi.",
                        "Ponovo pokrenite obradu samo za tog dobavljača.",
                        "Posle uspešnog importa napravite Snapshot i proverite Deltu.",
                    ],
                },
            )
        except Exception:
            await self.session.rollback()
            logging.getLogger(__name__).exception(
                "Pipeline incident sync failed source_id=%s run_id=%s",
                context.source.id,
                context.run.id,
            )

    async def resolve_after_success(self, context: PipelineContext) -> int:
        """Resolve only pipeline incidents owned by the successful source."""
        incidents = await self.support.repository.active_pipeline_incidents(
            context.source.id
        )
        if not incidents:
            return 0
        resolved_at = datetime.now(UTC)
        for incident in incidents:
            await self.support.repository.mutate(
                incident,
                {
                    "status": "RESOLVED",
                    "resolved_at": resolved_at,
                    "resolved_by": self.support.actor,
                    "resolution_code": "PIPELINE_RECOVERED",
                    "resolution_summary": (
                        "Sledeći kompletan pipeline za isti izvor uspešno je završen."
                    ),
                    "version": incident.version + 1,
                },
                [
                    self.support.event(
                        incident.id,
                        "RESOLVED",
                        incident.status,
                        "RESOLVED",
                        {
                            "pipeline_run_id": str(context.run.id),
                            "reason": "successful_full_pipeline",
                        },
                    )
                ],
            )
        await self.session.commit()
        return len(incidents)

    @staticmethod
    def _recommended_action(code: str) -> str:
        if code == "pipeline_active_contract_missing":
            return "Aktivirajte analizu i mapiranje, pa ponovo pokrenite pipeline."
        if code == "pipeline_schema_incompatible":
            return "Pregledajte promene polja i uradite novo mapiranje pre importa."
        if code == "acquisition_http_failed":
            return "Proverite dostupnost dobavljača i pristupne podatke, zatim ponovite preuzimanje."
        if code in {
            "pipeline_worker_dead_letter",
            "pipeline_worker_execution_failed",
            "pipeline_worker_terminal_mismatch",
        }:
            return "Pipeline je oslobođen. Pregledajte incident i ponovo pokrenite preuzimanje."
        return "Pregledajte fazu neuspeha i ponovite obradu nakon otklanjanja uzroka."


__all__ = ["SupplierPipelineIncidentService"]
