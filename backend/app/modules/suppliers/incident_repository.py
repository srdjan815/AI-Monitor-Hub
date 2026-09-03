from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.delta_models import SupplierDeltaRun
from app.modules.suppliers.incident_models import (
    SupplierIncident,
    SupplierIncidentComment,
    SupplierIncidentEvent,
    SupplierIncidentLink,
    SupplierIncidentRule,
)
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.snapshot_models import (
    SupplierSnapshot,
    SupplierSnapshotArchiveOperation,
)


class SupplierIncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def supplier(self, supplier_id: uuid.UUID) -> Supplier | None:
        return await self.session.get(Supplier, supplier_id)

    async def source(self, source_id: uuid.UUID) -> SupplierSource | None:
        return await self.session.get(SupplierSource, source_id)

    async def acquisition(self, run_id: uuid.UUID) -> SupplierAcquisitionRun | None:
        return await self.session.get(SupplierAcquisitionRun, run_id)

    async def snapshot(self, snapshot_id: uuid.UUID) -> SupplierSnapshot | None:
        return await self.session.get(SupplierSnapshot, snapshot_id)

    async def archive_operation(
        self, operation_id: uuid.UUID
    ) -> SupplierSnapshotArchiveOperation | None:
        return await self.session.get(SupplierSnapshotArchiveOperation, operation_id)

    async def delta(self, delta_id: uuid.UUID) -> SupplierDeltaRun | None:
        return await self.session.get(SupplierDeltaRun, delta_id)

    async def get(
        self, incident_id: uuid.UUID, *, lock: bool = False
    ) -> SupplierIncident | None:
        query = select(SupplierIncident).where(SupplierIncident.id == incident_id)
        if lock:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def by_fingerprint(
        self, fingerprint: str, *, lock: bool = False
    ) -> SupplierIncident | None:
        query = (
            select(SupplierIncident)
            .where(SupplierIncident.fingerprint == fingerprint)
            .order_by(SupplierIncident.created_at.desc())
            .limit(1)
        )
        if lock:
            query = query.with_for_update()
        return (await self.session.execute(query)).scalar_one_or_none()

    async def active_pipeline_incidents(
        self, source_id: uuid.UUID
    ) -> list[SupplierIncident]:
        rows = await self.session.execute(
            select(SupplierIncident)
            .where(
                SupplierIncident.source_connection_id == source_id,
                SupplierIncident.source_domain == "PIPELINE",
                SupplierIncident.status.in_(
                    ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "SUPPRESSED")
                ),
            )
            .order_by(SupplierIncident.created_at, SupplierIncident.id)
            .with_for_update()
        )
        return list(rows.scalars())

    async def add_incident(
        self, incident: SupplierIncident, event: SupplierIncidentEvent
    ) -> None:
        self.session.add(incident)
        await self.session.flush()
        event.incident_id = incident.id
        self.session.add(event)
        await self.session.flush()

    async def mutate(
        self,
        incident: SupplierIncident,
        changes: dict[str, object],
        events: list[SupplierIncidentEvent],
    ) -> None:
        for field, value in changes.items():
            setattr(incident, field, value)
        self.session.add_all(events)
        await self.session.flush()

    async def add_comment(
        self, comment: SupplierIncidentComment, event: SupplierIncidentEvent
    ) -> None:
        self.session.add_all([comment, event])
        await self.session.flush()

    async def add_link(
        self, link: SupplierIncidentLink, event: SupplierIncidentEvent
    ) -> None:
        self.session.add_all([link, event])
        await self.session.flush()

    async def events(
        self, incident_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[SupplierIncidentEvent], int]:
        total = await self.session.scalar(
            select(func.count(SupplierIncidentEvent.id)).where(
                SupplierIncidentEvent.incident_id == incident_id
            )
        )
        rows = await self.session.execute(
            select(SupplierIncidentEvent)
            .where(SupplierIncidentEvent.incident_id == incident_id)
            .order_by(
                SupplierIncidentEvent.created_at.desc(),
                SupplierIncidentEvent.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def comments(
        self, incident_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[SupplierIncidentComment], int]:
        total = await self.session.scalar(
            select(func.count(SupplierIncidentComment.id)).where(
                SupplierIncidentComment.incident_id == incident_id
            )
        )
        rows = await self.session.execute(
            select(SupplierIncidentComment)
            .where(SupplierIncidentComment.incident_id == incident_id)
            .order_by(
                SupplierIncidentComment.created_at.desc(),
                SupplierIncidentComment.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def links(self, incident_id: uuid.UUID) -> list[SupplierIncidentLink]:
        rows = await self.session.execute(
            select(SupplierIncidentLink)
            .where(
                or_(
                    SupplierIncidentLink.incident_id == incident_id,
                    SupplierIncidentLink.related_incident_id == incident_id,
                )
            )
            .order_by(SupplierIncidentLink.created_at)
        )
        return list(rows.scalars())

    async def list_incidents(
        self,
        *,
        supplier_id: uuid.UUID | None,
        source_id: uuid.UUID | None,
        status: str | None,
        severity: str | None,
        priority: str | None,
        incident_type: str | None,
        source_domain: str | None,
        assigned_user: str | None,
        unassigned: bool | None,
        overdue: bool | None,
        created_from: datetime | None,
        created_to: datetime | None,
        search: str | None,
        limit: int,
        offset: int,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[SupplierIncident], int]:
        filters: list[Any] = []
        for column, value in (
            (SupplierIncident.supplier_id, supplier_id),
            (SupplierIncident.source_connection_id, source_id),
            (SupplierIncident.status, status),
            (SupplierIncident.severity, severity),
            (SupplierIncident.priority, priority),
            (SupplierIncident.incident_type, incident_type),
            (SupplierIncident.source_domain, source_domain),
            (SupplierIncident.assigned_user_id, assigned_user),
        ):
            if value is not None:
                filters.append(column == value)
        if unassigned is not None:
            filters.append(
                SupplierIncident.assigned_user_id.is_(None)
                if unassigned
                else SupplierIncident.assigned_user_id.is_not(None)
            )
        if overdue is not None:
            clause = (
                SupplierIncident.due_at < func.now()
            ) & SupplierIncident.status.in_(("OPEN", "ACKNOWLEDGED", "IN_PROGRESS"))
            filters.append(clause if overdue else ~clause)
        if created_from:
            filters.append(SupplierIncident.created_at >= created_from)
        if created_to:
            filters.append(SupplierIncident.created_at <= created_to)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    SupplierIncident.incident_code.ilike(pattern),
                    SupplierIncident.title.ilike(pattern),
                )
            )
        sort_columns = {
            "created_at": SupplierIncident.created_at,
            "updated_at": SupplierIncident.updated_at,
            "incident_code": SupplierIncident.incident_code,
            "severity": SupplierIncident.severity,
            "priority": SupplierIncident.priority,
            "status": SupplierIncident.status,
            "due_at": SupplierIncident.due_at,
        }
        primary = sort_columns[sort_by]
        ordering = primary.asc() if sort_order == "asc" else primary.desc()
        total = await self.session.scalar(
            select(func.count(SupplierIncident.id)).where(*filters)
        )
        rows = await self.session.execute(
            select(SupplierIncident)
            .where(*filters)
            .order_by(ordering, SupplierIncident.id.asc() if sort_order == "asc" else SupplierIncident.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def summary(
        self, supplier_id: uuid.UUID | None
    ) -> list[tuple[str, str, str, int]]:
        filters = [SupplierIncident.supplier_id == supplier_id] if supplier_id else []
        rows = await self.session.execute(
            select(
                SupplierIncident.status,
                SupplierIncident.priority,
                SupplierIncident.severity,
                func.count(),
            )
            .where(*filters)
            .group_by(
                SupplierIncident.status,
                SupplierIncident.priority,
                SupplierIncident.severity,
            )
        )
        return [(str(a), str(b), str(c), int(d)) for a, b, c, d in rows]

    async def matching_rules(
        self, domain: str, signal: str | None
    ) -> list[SupplierIncidentRule]:
        rows = await self.session.execute(
            select(SupplierIncidentRule).where(
                SupplierIncidentRule.source_domain == domain,
                or_(
                    SupplierIncidentRule.signal_code == signal,
                    SupplierIncidentRule.signal_code.is_(None),
                ),
            )
        )
        return list(rows.scalars())

    async def add_rule(self, rule: SupplierIncidentRule) -> None:
        self.session.add(rule)
        await self.session.flush()

    async def get_rule(self, rule_id: uuid.UUID) -> SupplierIncidentRule | None:
        return await self.session.get(SupplierIncidentRule, rule_id)

    async def list_rules(
        self, *, limit: int, offset: int
    ) -> tuple[list[SupplierIncidentRule], int]:
        total = await self.session.scalar(
            select(func.count(SupplierIncidentRule.id)).where(
                SupplierIncidentRule.is_active.is_(True)
            )
        )
        rows = await self.session.execute(
            select(SupplierIncidentRule)
            .where(SupplierIncidentRule.is_active.is_(True))
            .order_by(
                SupplierIncidentRule.created_at.desc(),
                SupplierIncidentRule.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars()), int(total or 0)

    async def mutate_rule(
        self, rule: SupplierIncidentRule, changes: dict[str, object]
    ) -> None:
        for name, value in changes.items():
            setattr(rule, name, value)
        await self.session.flush()


__all__ = ["SupplierIncidentRepository"]
