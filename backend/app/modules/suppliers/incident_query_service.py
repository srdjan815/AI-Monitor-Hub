from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.incident_models import SupplierIncident
from app.modules.suppliers.incident_repository import SupplierIncidentRepository


class SupplierIncidentQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = SupplierIncidentRepository(session)

    async def get(self, incident_id: uuid.UUID) -> SupplierIncident:
        incident = await self.repository.get(incident_id)
        if incident is None:
            supplier_error(404, "incident_not_found", "Incident nije pronađen")
        return incident

    async def summary(self, supplier_id: uuid.UUID | None) -> dict[str, object]:
        rows = await self.repository.summary(supplier_id)
        statuses = {
            name: 0
            for name in (
                "OPEN",
                "ACKNOWLEDGED",
                "IN_PROGRESS",
                "RESOLVED",
                "DISMISSED",
                "SUPPRESSED",
            )
        }
        priorities = {name: 0 for name in ("P1", "P2", "P3", "P4")}
        active = {"OPEN", "ACKNOWLEDGED", "IN_PROGRESS"}
        total_active = high = 0
        for status, priority, severity, count in rows:
            statuses[status] = statuses.get(status, 0) + count
            if status in active:
                total_active += count
                priorities[priority] += count
                if severity in {"HIGH", "CRITICAL"}:
                    high += count
        incidents, _ = await self.repository.list_incidents(
            supplier_id=supplier_id,
            source_id=None,
            status=None,
            severity=None,
            priority=None,
            incident_type=None,
            source_domain=None,
            assigned_user=None,
            unassigned=None,
            overdue=None,
            created_from=None,
            created_to=None,
            search=None,
            limit=500,
            offset=0,
        )
        now = datetime.now(UTC)
        return {
            "total_active": total_active,
            "open": statuses["OPEN"],
            "acknowledged": statuses["ACKNOWLEDGED"],
            "in_progress": statuses["IN_PROGRESS"],
            "resolved": statuses["RESOLVED"],
            "dismissed": statuses["DISMISSED"],
            "suppressed": statuses["SUPPRESSED"],
            "priorities": priorities,
            "high_or_critical_active": high,
            "overdue": sum(
                row.status in active and row.due_at is not None and row.due_at < now
                for row in incidents
            ),
            "unassigned": sum(
                row.status in active and row.assigned_user_id is None
                for row in incidents
            ),
        }


__all__ = ["SupplierIncidentQueryService"]
