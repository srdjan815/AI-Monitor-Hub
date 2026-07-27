from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.acquisition_models import SupplierAcquisitionRun
from app.modules.suppliers.delta_models import SupplierDeltaRun
from app.modules.suppliers.incident_models import SupplierIncident
from app.modules.suppliers.models import Supplier, SupplierSource
from app.modules.suppliers.snapshot_models import SupplierSnapshot


class SupplierApiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scalar_count(self, query: Select[tuple[int]]) -> int:
        return int(await self.session.scalar(query) or 0)

    async def overview_counts(
        self,
        *,
        range_from: datetime,
        range_to: datetime,
    ) -> dict[str, int]:
        active_statuses = ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS")
        queries = {
            "active_suppliers": select(func.count(Supplier.id)).where(
                Supplier.is_active.is_(True)
            ),
            "active_source_connections": select(func.count(SupplierSource.id)).where(
                SupplierSource.is_active.is_(True)
            ),
            "recent_acquisitions": select(
                func.count(SupplierAcquisitionRun.id)
            ).where(
                SupplierAcquisitionRun.created_at.between(range_from, range_to)
            ),
            "failed_acquisitions": select(
                func.count(SupplierAcquisitionRun.id)
            ).where(
                SupplierAcquisitionRun.status == "FAILED",
                SupplierAcquisitionRun.created_at.between(range_from, range_to),
            ),
            "ready_snapshots": select(func.count(SupplierSnapshot.id)).where(
                SupplierSnapshot.status == "READY"
            ),
            "archived_snapshots": select(func.count(SupplierSnapshot.id)).where(
                SupplierSnapshot.storage_state == "ARCHIVED"
            ),
            "recent_deltas": select(func.count(SupplierDeltaRun.id)).where(
                SupplierDeltaRun.created_at.between(range_from, range_to)
            ),
            "active_incidents": select(func.count(SupplierIncident.id)).where(
                SupplierIncident.status.in_(active_statuses)
            ),
            "overdue_incidents": select(func.count(SupplierIncident.id)).where(
                SupplierIncident.status.in_(active_statuses),
                SupplierIncident.due_at < func.now(),
            ),
            "unassigned_incidents": select(func.count(SupplierIncident.id)).where(
                SupplierIncident.status.in_(active_statuses),
                SupplierIncident.assigned_user_id.is_(None),
            ),
        }
        return {
            name: await self.scalar_count(query)
            for name, query in queries.items()
        }

    @staticmethod
    def _operation_query(
        model: Any,
        resource_type: str,
        code_column: Any,
        status_column: Any,
        path_prefix: str,
        *,
        failed_only: bool,
    ) -> Select[Any]:
        query = select(
            literal(resource_type).label("resource_type"),
            model.id.label("id"),
            code_column.label("code"),
            status_column.label("status"),
            model.created_at.label("occurred_at"),
            (literal(path_prefix) + cast(model.id, String)).label(
                "resource_path"
            ),
        )
        if failed_only:
            query = query.where(status_column == "FAILED")
        return query

    async def operations(
        self,
        *,
        allowed: set[str],
        failed_only: bool,
        limit: int,
    ) -> list[dict[str, object]]:
        definitions = (
            (
                SupplierAcquisitionRun,
                "acquisition",
                SupplierAcquisitionRun.acquisition_code,
                SupplierAcquisitionRun.status,
                "/api/v1/suppliers/platform/acquisitions/",
            ),
            (
                SupplierSnapshot,
                "snapshot",
                SupplierSnapshot.snapshot_code,
                SupplierSnapshot.status,
                "/api/v1/suppliers/platform/snapshots/",
            ),
            (
                SupplierDeltaRun,
                "delta",
                SupplierDeltaRun.delta_code,
                SupplierDeltaRun.status,
                "/api/v1/suppliers/platform/deltas/",
            ),
        )
        queries = [
            self._operation_query(*definition, failed_only=failed_only)
            for definition in definitions
            if definition[1] in allowed
        ]
        if not queries:
            return []
        combined = union_all(*queries).subquery()
        rows = await self.session.execute(
            select(combined)
            .order_by(combined.c.occurred_at.desc(), combined.c.id.desc())
            .limit(limit)
        )
        return [dict(row._mapping) for row in rows]

    @staticmethod
    def _search_query(
        model: Any,
        resource_type: str,
        code_column: Any,
        name_column: Any,
        status_column: Any,
        path_prefix: str,
        pattern: str,
        exact: str,
    ) -> Select[Any]:
        return select(
            literal(resource_type).label("resource_type"),
            model.id.label("id"),
            code_column.label("code"),
            name_column.label("display_name"),
            literal(None).label("short_context"),
            status_column.label("status"),
            (literal(path_prefix) + cast(model.id, String)).label(
                "resource_path"
            ),
            case((func.lower(code_column) == exact, 2), else_=1).label("rank"),
        ).where(or_(code_column.ilike(pattern), name_column.ilike(pattern)))

    async def search(
        self,
        query: str,
        *,
        allowed: set[str],
        limit: int,
    ) -> list[dict[str, object]]:
        pattern = f"%{query}%"
        exact = query.lower()
        definitions = (
            (
                Supplier,
                "supplier",
                Supplier.supplier_code,
                Supplier.company_name,
                Supplier.status,
                "/api/v1/suppliers/",
            ),
            (
                SupplierSource,
                "source_connection",
                SupplierSource.source_code,
                SupplierSource.name,
                SupplierSource.status,
                "/api/v1/suppliers/platform/sources/",
            ),
            (
                SupplierAcquisitionRun,
                "acquisition",
                SupplierAcquisitionRun.acquisition_code,
                SupplierAcquisitionRun.acquisition_code,
                SupplierAcquisitionRun.status,
                "/api/v1/suppliers/platform/acquisitions/",
            ),
            (
                SupplierSnapshot,
                "snapshot",
                SupplierSnapshot.snapshot_code,
                SupplierSnapshot.snapshot_code,
                SupplierSnapshot.status,
                "/api/v1/suppliers/platform/snapshots/",
            ),
            (
                SupplierDeltaRun,
                "delta",
                SupplierDeltaRun.delta_code,
                SupplierDeltaRun.delta_code,
                SupplierDeltaRun.status,
                "/api/v1/suppliers/platform/deltas/",
            ),
            (
                SupplierIncident,
                "incident",
                SupplierIncident.incident_code,
                SupplierIncident.title,
                SupplierIncident.status,
                "/api/v1/suppliers/incidents/",
            ),
        )
        queries = [
            self._search_query(
                definition[0],
                definition[1],
                definition[2],
                definition[3],
                definition[4],
                definition[5],
                pattern=pattern,
                exact=exact,
            )
            for definition in definitions
            if definition[1] in allowed
        ]
        if not queries:
            return []
        combined = union_all(*queries).subquery()
        rows = await self.session.execute(
            select(combined)
            .order_by(combined.c.rank.desc(), combined.c.code, combined.c.id)
            .limit(limit + 1)
        )
        return [dict(row._mapping) for row in rows]


__all__ = ["SupplierApiRepository"]
