from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import current_actor_id
from app.modules.suppliers.incident_models import (
    SupplierIncident,
    SupplierIncidentEvent,
)
from app.modules.suppliers.incident_repository import SupplierIncidentRepository
from app.modules.suppliers.incident_safety import (
    incident_fingerprint,
    sanitize_context,
    sanitize_text,
)
from app.modules.suppliers.errors import supplier_error


class SupplierIncidentSupport:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierIncidentRepository(session)

    @property
    def actor(self) -> str:
        return current_actor_id() or "system"

    def event(
        self,
        incident_id: uuid.UUID,
        event_type: str,
        previous: str | None,
        current: str | None,
        data: dict[str, object] | None = None,
    ) -> SupplierIncidentEvent:
        return SupplierIncidentEvent(
            incident_id=incident_id,
            event_type=event_type,
            actor_id=self.actor,
            previous_status=previous,
            current_status=current,
            event_data=sanitize_context(data or {}),
        )

    async def create_or_occurrence(
        self,
        *,
        incident_id: uuid.UUID,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
        source_domain: str,
        incident_type: str,
        severity: str,
        priority: str,
        title: str,
        description: str,
        source_entity_id: uuid.UUID,
        context: dict[str, object],
        due_at: datetime | None = None,
        assigned_user_id: str | None = None,
        acquisition_id: uuid.UUID | None = None,
        snapshot_id: uuid.UUID | None = None,
        operation_id: uuid.UUID | None = None,
        delta_id: uuid.UUID | None = None,
    ) -> SupplierIncident:
        now = datetime.now(UTC)
        fingerprint = incident_fingerprint(
            {
                "supplier_id": supplier_id,
                "source_id": source_id,
                "domain": source_domain,
                "type": incident_type,
                "entity_id": source_entity_id,
            }
        )
        existing = await self.repository.by_fingerprint(fingerprint, lock=True)
        if existing and existing.status != "DISMISSED":
            return await self.record_occurrence(existing, now)
        due_hours = {
            "P1": settings.incident_due_hours_p1,
            "P2": settings.incident_due_hours_p2,
            "P3": settings.incident_due_hours_p3,
            "P4": settings.incident_due_hours_p4,
        }
        incident = SupplierIncident(
            id=incident_id,
            supplier_id=supplier_id,
            source_connection_id=source_id,
            incident_type=incident_type,
            source_domain=source_domain,
            severity=severity,
            priority=priority,
            status="OPEN",
            title=sanitize_text(title, 300),
            description=sanitize_text(description, 2000),
            fingerprint=fingerprint,
            correlation_key=f"{source_domain}:{source_entity_id}",
            occurrence_count=1,
            first_detected_at=now,
            last_detected_at=now,
            due_at=due_at or now + timedelta(hours=due_hours[priority]),
            assigned_user_id=(
                sanitize_text(assigned_user_id, 255) if assigned_user_id else None
            ),
            created_by=self.actor,
            source_acquisition_run_id=acquisition_id,
            source_snapshot_id=snapshot_id,
            source_snapshot_archive_operation_id=operation_id,
            source_delta_run_id=delta_id,
            sanitized_context=sanitize_context(context),
        )
        try:
            await self.repository.add_incident(
                incident,
                self.event(
                    incident.id,
                    "CREATED",
                    None,
                    "OPEN",
                    {"source_domain": source_domain},
                ),
            )
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            concurrent = await self.repository.by_fingerprint(fingerprint, lock=True)
            if concurrent:
                return await self.record_occurrence(concurrent)
            raise
        await self.session.refresh(incident)
        return incident

    async def record_occurrence(
        self,
        incident: SupplierIncident,
        now: datetime | None = None,
    ) -> SupplierIncident:
        detected = now or datetime.now(UTC)
        changes: dict[str, object] = {
            "occurrence_count": incident.occurrence_count + 1,
            "last_detected_at": detected,
            "version": incident.version + 1,
        }
        events = [
            self.event(
                incident.id,
                "OCCURRENCE",
                incident.status,
                incident.status,
                {"occurrence_count": incident.occurrence_count + 1},
            )
        ]
        expired = (
            incident.status == "SUPPRESSED"
            and incident.suppression_until is not None
            and incident.suppression_until <= detected
        )
        if incident.status == "RESOLVED" or expired:
            if expired:
                events.append(
                    self.event(
                        incident.id,
                        "SUPPRESSION_EXPIRED",
                        "SUPPRESSED",
                        "OPEN",
                    )
                )
            events.append(
                self.event(incident.id, "REOPENED", incident.status, "OPEN")
            )
            changes.update(
                {
                    "status": "OPEN",
                    "reopened_at": detected,
                    "suppression_until": None,
                }
            )
        await self.repository.mutate(incident, changes, events)
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def incident(
        self,
        incident_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> SupplierIncident:
        incident = await self.repository.get(incident_id, lock=lock)
        if incident is None:
            supplier_error(404, "incident_not_found", "Incident nije pronađen")
        return incident

    async def validate_scope(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID | None,
    ) -> None:
        if await self.repository.supplier(supplier_id) is None:
            supplier_error(404, "supplier_not_found", "Dobavljač nije pronađen")
        if source_id:
            source = await self.repository.source(source_id)
            if source is None or source.supplier_id != supplier_id:
                supplier_error(
                    404,
                    "supplier_source_not_found",
                    "Izvor nije pronađen",
                )


__all__ = ["SupplierIncidentSupport"]
