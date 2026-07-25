from __future__ import annotations

import uuid
from typing import cast

from app.core.config import settings
from app.modules.suppliers.incident_contracts import DEFAULT_PRIORITY, SIGNAL_TO_INCIDENT
from app.modules.suppliers.incident_models import SupplierIncident, SupplierIncidentRule
from app.modules.suppliers.incident_rules import rule_allows, select_rule
from app.modules.suppliers.incident_support import SupplierIncidentSupport
from app.modules.suppliers.errors import supplier_error


class SupplierIncidentSyncService(SupplierIncidentSupport):
    async def sync_acquisition(
        self,
        run_id: uuid.UUID,
        *,
        preview: bool = False,
    ) -> list[SupplierIncident] | list[dict[str, object]]:
        run = await self.repository.acquisition(run_id)
        if run is None:
            supplier_error(
                404,
                "acquisition_run_not_found",
                "Acquisition Run nije pronađen",
            )
        candidates: list[dict[str, object]] = []
        if run.status == "FAILED":
            incident_type = self.acquisition_type(run.failure_code)
            candidates.append(
                self.candidate(
                    "ACQUISITION",
                    incident_type,
                    run.failure_code or "ACQUISITION_FAILED",
                    "HIGH",
                    {
                        "failure_code": run.failure_code,
                        "failure_message": run.failure_message,
                        "acquisition_code": run.acquisition_code,
                    },
                )
            )
        if run.status == "CANCELLED":
            candidates.append(
                self.candidate(
                    "ACQUISITION",
                    "ACQUISITION_CANCELLED_UNEXPECTEDLY",
                    "ACQUISITION_CANCELLED_UNEXPECTEDLY",
                    "MEDIUM",
                    {"acquisition_code": run.acquisition_code},
                )
            )
        if (
            run.total_record_count
            and run.rejected_record_count / run.total_record_count >= 0.5
        ):
            candidates.append(
                self.candidate(
                    "ACQUISITION",
                    "HIGH_REJECTED_ROW_RATIO",
                    "HIGH_REJECTED_ROW_RATIO",
                    "HIGH",
                    {
                        "rejected": run.rejected_record_count,
                        "total": run.total_record_count,
                        "ratio": run.rejected_record_count
                        / run.total_record_count,
                    },
                )
            )
        if preview:
            return candidates
        return await self.sync_candidates(
            run.supplier_id,
            run.source_connection_id,
            run.id,
            candidates,
            acquisition_id=run.id,
        )

    async def sync_snapshot(
        self,
        snapshot_id: uuid.UUID,
        operation_id: uuid.UUID | None = None,
        *,
        preview: bool = False,
    ) -> list[SupplierIncident] | list[dict[str, object]]:
        snapshot = await self.repository.snapshot(snapshot_id)
        if snapshot is None:
            supplier_error(404, "snapshot_not_found", "Snapshot nije pronađen")
        candidates: list[dict[str, object]] = []
        if snapshot.status == "FAILED":
            incident_type = (
                "SNAPSHOT_INTEGRITY_FAILURE"
                if snapshot.failure_code and "fingerprint" in snapshot.failure_code
                else "SNAPSHOT_BUILD_FAILED"
            )
            candidates.append(
                self.candidate(
                    "SNAPSHOT",
                    incident_type,
                    snapshot.failure_code or incident_type,
                    "HIGH",
                    {
                        "snapshot_code": snapshot.snapshot_code,
                        "failure_code": snapshot.failure_code,
                        "failure_message": snapshot.failure_message,
                    },
                )
            )
        operation = (
            await self.repository.archive_operation(operation_id)
            if operation_id
            else None
        )
        if operation_id and (
            operation is None or operation.snapshot_id != snapshot.id
        ):
            supplier_error(
                404,
                "snapshot_archive_operation_not_found",
                "Archive operacija nije pronađena",
            )
        if operation and operation.status == "FAILED":
            code = operation.failure_code or "SNAPSHOT_ARCHIVE_FAILED"
            incident_type = (
                "SNAPSHOT_ARCHIVE_CORRUPTED"
                if "checksum" in code or "corrupt" in code
                else "SNAPSHOT_ARCHIVE_FAILED"
            )
            candidates.append(
                self.candidate(
                    "SNAPSHOT",
                    incident_type,
                    code,
                    "HIGH",
                    {
                        "snapshot_code": snapshot.snapshot_code,
                        "operation_id": str(operation.id),
                        "failure_code": code,
                    },
                )
            )
        if preview:
            return candidates
        return await self.sync_candidates(
            snapshot.supplier_id,
            snapshot.source_connection_id,
            snapshot.id,
            candidates,
            snapshot_id=snapshot.id,
            operation_id=operation.id if operation else None,
        )

    async def sync_delta(
        self,
        delta_id: uuid.UUID,
        *,
        preview: bool = False,
    ) -> list[SupplierIncident] | list[dict[str, object]]:
        delta = await self.repository.delta(delta_id)
        if delta is None:
            supplier_error(404, "delta_not_found", "Delta Run nije pronađen")
        candidates: list[dict[str, object]] = []
        if delta.status == "FAILED":
            incident_type = (
                "DELTA_DUPLICATE_IDENTITY"
                if delta.failure_code == "DUPLICATE_IDENTITY"
                else "DELTA_CALCULATION_FAILED"
            )
            candidates.append(
                self.candidate(
                    "DELTA",
                    incident_type,
                    delta.failure_code or incident_type,
                    "HIGH",
                    {
                        "delta_code": delta.delta_code,
                        "failure_code": delta.failure_code,
                        "failure_message": delta.failure_message,
                    },
                )
            )
        for signal in delta.anomaly_signals:
            code = str(signal.get("code", ""))
            signal_type = SIGNAL_TO_INCIDENT.get(code)
            if signal_type:
                candidates.append(
                    self.candidate(
                        "DELTA",
                        signal_type,
                        code,
                        self.signal_severity(code),
                        {
                            "delta_code": delta.delta_code,
                            "signal": signal,
                            "comparison_version": delta.comparison_version,
                        },
                    )
                )
        if preview:
            return candidates
        return await self.sync_candidates(
            delta.supplier_id,
            delta.source_connection_id,
            delta.id,
            candidates,
            delta_id=delta.id,
        )

    async def sync_candidates(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
        entity_id: uuid.UUID,
        candidates: list[dict[str, object]],
        acquisition_id: uuid.UUID | None = None,
        snapshot_id: uuid.UUID | None = None,
        operation_id: uuid.UUID | None = None,
        delta_id: uuid.UUID | None = None,
    ) -> list[SupplierIncident]:
        if len(candidates) > settings.incident_max_synchronized_per_source:
            supplier_error(
                409,
                "incident_sync_limit_exceeded",
                "Previše Incident kandidata",
            )
        results: list[SupplierIncident] = []
        for candidate in candidates:
            rule = await self.rule(
                str(candidate["source_domain"]),
                str(candidate["signal_code"]),
                supplier_id,
                source_id,
            )
            if rule is False:
                continue
            context = cast(dict[str, object], candidate["context"])
            if isinstance(rule, SupplierIncidentRule) and not rule_allows(
                rule, context
            ):
                continue
            severity = (
                rule.resulting_severity
                if isinstance(rule, SupplierIncidentRule)
                else str(candidate["severity"])
            )
            priority = (
                rule.default_priority
                if isinstance(rule, SupplierIncidentRule)
                else DEFAULT_PRIORITY[severity]
            )
            results.append(
                await self.create_or_occurrence(
                    incident_id=uuid.uuid4(),
                    supplier_id=supplier_id,
                    source_id=source_id,
                    source_domain=str(candidate["source_domain"]),
                    incident_type=str(candidate["incident_type"]),
                    severity=severity,
                    priority=priority,
                    title=str(candidate["incident_type"])
                    .replace("_", " ")
                    .title(),
                    description=(
                        f"Automatski Incident iz "
                        f"{candidate['source_domain']} činjenice."
                    ),
                    source_entity_id=entity_id,
                    context=context,
                    acquisition_id=acquisition_id,
                    snapshot_id=snapshot_id,
                    operation_id=operation_id,
                    delta_id=delta_id,
                )
            )
        return results

    async def rule(
        self,
        domain: str,
        signal: str,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
    ) -> SupplierIncidentRule | bool | None:
        rule = select_rule(
            await self.repository.matching_rules(domain, signal),
            supplier_id,
            source_id,
        )
        if rule:
            return rule if rule.enabled else False
        return False if signal == "IMAGE_SET_CHANGED" else None

    @staticmethod
    def candidate(
        domain: str,
        incident_type: str,
        signal: str,
        severity: str,
        context: dict[str, object],
    ) -> dict[str, object]:
        return {
            "source_domain": domain,
            "incident_type": incident_type,
            "signal_code": signal,
            "severity": severity,
            "context": context,
        }

    @staticmethod
    def signal_severity(code: str) -> str:
        return (
            "HIGH"
            if code
            in {
                "HIGH_REMOVAL_RATIO",
                "LARGE_PRICE_INCREASE",
                "ALL_STOCK_BECAME_UNAVAILABLE",
            }
            else "MEDIUM"
        )

    @staticmethod
    def acquisition_type(code: str | None) -> str:
        supported = {
            "SOURCE_UNAVAILABLE",
            "SOURCE_AUTHENTICATION_FAILED",
            "SECRET_RESOLUTION_FAILED",
            "UNSUPPORTED_SOURCE_EXECUTION",
            "MALFORMED_SOURCE_FILE",
            "UNSUPPORTED_SOURCE_FORMAT",
            "FILE_SIZE_LIMIT_EXCEEDED",
            "RECORD_COUNT_LIMIT_EXCEEDED",
        }
        return code if code in supported else "ACQUISITION_FAILED"


__all__ = ["SupplierIncidentSyncService"]
