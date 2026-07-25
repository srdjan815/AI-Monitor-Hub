from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from app.core.security import INCIDENTS_MANAGE, current_principal
from app.modules.suppliers.incident_contracts import ALLOWED_TRANSITIONS
from app.modules.suppliers.incident_models import (
    SupplierIncident,
    SupplierIncidentComment,
    SupplierIncidentLink,
)
from app.modules.suppliers.incident_safety import sanitize_text
from app.modules.suppliers.incident_schemas import ManualIncidentCreate
from app.modules.suppliers.incident_support import SupplierIncidentSupport
from app.modules.suppliers.errors import supplier_error


class SupplierIncidentService(SupplierIncidentSupport):
    async def manual(self, payload: ManualIncidentCreate) -> SupplierIncident:
        await self.validate_scope(payload.supplier_id, payload.source_connection_id)
        principal = current_principal()
        if (
            payload.severity == "CRITICAL" or payload.priority.value == "P1"
        ) and (principal is None or INCIDENTS_MANAGE not in principal.permissions):
            supplier_error(
                403,
                "incident_elevated_permission_required",
                "CRITICAL/P1 zahteva incidents.manage",
            )
        identifier = uuid.uuid4()
        return await self.create_or_occurrence(
            incident_id=identifier,
            supplier_id=payload.supplier_id,
            source_id=payload.source_connection_id,
            source_domain="MANUAL",
            incident_type=payload.incident_type,
            severity=payload.severity,
            priority=payload.priority.value,
            title=payload.title,
            description=payload.description,
            source_entity_id=identifier,
            due_at=payload.due_at,
            assigned_user_id=payload.assigned_user_id,
            context={"origin": "MANUAL"},
        )

    async def transition(
        self,
        incident_id: uuid.UUID,
        target: str,
        *,
        reason: str | None = None,
        resolution_code: str | None = None,
        suppression_until: datetime | None = None,
    ) -> SupplierIncident:
        incident = await self.incident(incident_id, lock=True)
        if target not in ALLOWED_TRANSITIONS.get(incident.status, set()):
            supplier_error(
                409,
                "incident_transition_invalid",
                "Status tranzicija nije dozvoljena",
            )
        if target == "RESOLVED" and (not resolution_code or not reason):
            supplier_error(
                422,
                "incident_resolution_required",
                "Resolution code i summary su obavezni",
            )
        if target in {"DISMISSED", "SUPPRESSED"} and not reason:
            supplier_error(
                422,
                "incident_reason_required",
                "Razlog je obavezan",
            )
        now = datetime.now(UTC)
        changes: dict[str, object] = {
            "status": target,
            "version": incident.version + 1,
        }
        if target == "ACKNOWLEDGED":
            changes["acknowledged_at"] = now
        if target == "RESOLVED":
            changes.update(
                {
                    "resolved_at": now,
                    "resolved_by": self.actor,
                    "resolution_code": resolution_code,
                    "resolution_summary": sanitize_text(reason or "", 1000),
                }
            )
        if target == "DISMISSED":
            changes.update(
                {
                    "dismissed_at": now,
                    "resolution_summary": sanitize_text(reason or "", 1000),
                }
            )
        if target == "SUPPRESSED":
            changes.update(
                {
                    "suppressed_at": now,
                    "suppression_until": suppression_until,
                    "resolution_summary": sanitize_text(reason or "", 1000),
                }
            )
        if target == "OPEN":
            changes.update({"reopened_at": now, "suppression_until": None})
        event_type = {
            "ACKNOWLEDGED": "ACKNOWLEDGED",
            "IN_PROGRESS": "INVESTIGATION_STARTED",
            "RESOLVED": "RESOLVED",
            "DISMISSED": "DISMISSED",
            "SUPPRESSED": "SUPPRESSED",
            "OPEN": "REOPENED",
        }[target]
        await self.repository.mutate(
            incident,
            changes,
            [
                self.event(
                    incident.id,
                    event_type,
                    incident.status,
                    target,
                    {"reason": sanitize_text(reason, 1000) if reason else None},
                )
            ],
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def assign(
        self,
        incident_id: uuid.UUID,
        user_id: str | None,
    ) -> SupplierIncident:
        incident = await self.incident(incident_id, lock=True)
        clean = sanitize_text(user_id, 255) if user_id else None
        if user_id and not clean:
            supplier_error(
                422,
                "incident_assignee_invalid",
                "Korisnički identitet nije validan",
            )
        await self.repository.mutate(
            incident,
            {
                "assigned_user_id": clean,
                "version": incident.version + 1,
            },
            [
                self.event(
                    incident.id,
                    "ASSIGNED" if clean else "UNASSIGNED",
                    incident.status,
                    incident.status,
                    {"assigned_user_id": clean},
                )
            ],
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return incident

    async def priority(
        self,
        incident_id: uuid.UUID,
        priority: str,
    ) -> SupplierIncident:
        return await self.simple_change(
            incident_id,
            {"priority": priority},
            "PRIORITY_CHANGED",
        )

    async def due_date(
        self,
        incident_id: uuid.UUID,
        due_at: datetime | None,
    ) -> SupplierIncident:
        return await self.simple_change(
            incident_id,
            {"due_at": due_at},
            "DUE_DATE_CHANGED",
        )

    async def comment(
        self,
        incident_id: uuid.UUID,
        body: str,
    ) -> SupplierIncidentComment:
        incident = await self.incident(incident_id)
        clean = sanitize_text(body, 4000)
        comment = SupplierIncidentComment(
            incident_id=incident.id,
            body=clean,
            created_by=self.actor,
        )
        await self.repository.add_comment(
            comment,
            self.event(
                incident.id,
                "COMMENT_ADDED",
                incident.status,
                incident.status,
                {"comment_length": len(clean)},
            ),
        )
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def link(
        self,
        incident_id: uuid.UUID,
        related_id: uuid.UUID,
        relationship: str,
    ) -> SupplierIncidentLink:
        incident = await self.incident(incident_id)
        related = await self.incident(related_id)
        link = SupplierIncidentLink(
            incident_id=incident.id,
            related_incident_id=related.id,
            relationship_type=relationship,
            created_by=self.actor,
        )
        await self.repository.add_link(
            link,
            self.event(
                incident.id,
                "RELATED",
                incident.status,
                incident.status,
                {
                    "related_incident_id": str(related.id),
                    "relationship": relationship,
                },
            ),
        )
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            supplier_error(
                409,
                "incident_link_exists",
                "Incident veza već postoji",
            )
        await self.session.refresh(link)
        return link

    async def simple_change(
        self,
        incident_id: uuid.UUID,
        changes: dict[str, object],
        event_type: str,
    ) -> SupplierIncident:
        incident = await self.incident(incident_id, lock=True)
        changes["version"] = incident.version + 1
        await self.repository.mutate(
            incident,
            changes,
            [
                self.event(
                    incident.id,
                    event_type,
                    incident.status,
                    incident.status,
                    changes,
                )
            ],
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return incident


__all__ = ["SupplierIncidentService"]
