from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    ACQUISITIONS_READ,
    DELTAS_READ,
    INCIDENTS_READ,
    SNAPSHOTS_READ,
    SUPPLIERS_READ,
    SUPPLIER_SOURCES_READ,
    current_principal,
)
from app.modules.suppliers.api_process_service import SupplierProcessOverviewService
from app.modules.suppliers.api_repository import SupplierApiRepository
from app.modules.suppliers.api_schemas import (
    BulkIncidentAssignRequest,
    BulkIncidentPriorityRequest,
    BulkItemResult,
    BulkOperationResponse,
    SupplierPlatformCount,
    SupplierPlatformOperation,
    SupplierPlatformOverview,
    SupplierPlatformSearchResponse,
    SupplierPlatformSearchResult,
)
from app.modules.suppliers.incident_models import SupplierIncident
from app.modules.suppliers.incident_service import SupplierIncidentService

_RESOURCE_PERMISSIONS = {
    "supplier": SUPPLIERS_READ,
    "source_connection": SUPPLIER_SOURCES_READ,
    "acquisition": ACQUISITIONS_READ,
    "snapshot": SNAPSHOTS_READ,
    "delta": DELTAS_READ,
    "incident": INCIDENTS_READ,
}
BulkCallable = Callable[[SupplierIncidentService], Awaitable[SupplierIncident]]


def _assign_operation(
    incident_id: uuid.UUID, assigned_user_id: str
) -> BulkCallable:
    async def execute(service: SupplierIncidentService) -> SupplierIncident:
        return await service.assign(incident_id, assigned_user_id)

    return execute


def _priority_operation(incident_id: uuid.UUID, priority: str) -> BulkCallable:
    async def execute(service: SupplierIncidentService) -> SupplierIncident:
        return await service.priority(incident_id, priority)

    return execute


class SupplierApiService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierApiRepository(session)

    @property
    def permissions(self) -> frozenset[str]:
        principal = current_principal()
        return principal.permissions if principal is not None else frozenset()

    def allowed_resources(self) -> set[str]:
        return {
            resource
            for resource, permission in _RESOURCE_PERMISSIONS.items()
            if permission in self.permissions
        }

    async def search(
        self, query: str, *, limit: int
    ) -> SupplierPlatformSearchResponse:
        rows = await self.repository.search(
            query.strip(), allowed=self.allowed_resources(), limit=limit
        )
        has_more = len(rows) > limit
        items = [
            SupplierPlatformSearchResult.model_validate(row) for row in rows[:limit]
        ]
        return SupplierPlatformSearchResponse(
            items=items, total=len(items), limit=limit, has_more=has_more
        )

    async def overview(
        self,
        *,
        range_from: datetime | None,
        range_to: datetime | None,
    ) -> SupplierPlatformOverview:
        end = range_to or datetime.now(UTC)
        start = range_from or end - timedelta(days=30)
        if start > end:
            raise HTTPException(
                422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "range_from ne sme biti posle range_to",
                },
            )
        if end - start > timedelta(days=366):
            raise HTTPException(
                422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "Pregled je ograničen na 366 dana",
                },
            )
        counts = await self.repository.overview_counts(
            range_from=start, range_to=end
        )
        allowed = self.allowed_resources()
        operation_types = allowed & {"acquisition", "snapshot", "delta"}
        latest = await self.repository.operations(
            allowed=operation_types, failed_only=False, limit=10
        )
        failures = await self.repository.operations(
            allowed=operation_types, failed_only=True, limit=10
        )
        latest_acquisition = await self.repository.operations(
            allowed=allowed & {"acquisition"},
            failed_only=False,
            limit=1,
        )

        def visible(name: str, resource: str) -> SupplierPlatformCount:
            permitted = resource in allowed
            return SupplierPlatformCount(
                value=counts[name] if permitted else None, permitted=permitted
            )

        return SupplierPlatformOverview(
            range_from=start,
            range_to=end,
            active_suppliers=visible("active_suppliers", "supplier"),
            active_source_connections=visible(
                "active_source_connections", "source_connection"
            ),
            recent_acquisitions=visible("recent_acquisitions", "acquisition"),
            failed_acquisitions=visible("failed_acquisitions", "acquisition"),
            ready_snapshots=visible("ready_snapshots", "snapshot"),
            archived_snapshots=visible("archived_snapshots", "snapshot"),
            recent_deltas=visible("recent_deltas", "delta"),
            active_incidents=visible("active_incidents", "incident"),
            overdue_incidents=visible("overdue_incidents", "incident"),
            unassigned_incidents=visible("unassigned_incidents", "incident"),
            latest_operations=[
                SupplierPlatformOperation.model_validate(row) for row in latest
            ],
            recent_failures=[
                SupplierPlatformOperation.model_validate(row) for row in failures
            ],
            latest_acquisition=(
                SupplierPlatformOperation.model_validate(latest_acquisition[0])
                if latest_acquisition
                else None
            ),
            supplier_processes=await SupplierProcessOverviewService(
                self.repository
            ).rows(),
        )

    async def bulk_assign(
        self, payload: BulkIncidentAssignRequest
    ) -> BulkOperationResponse:
        return await self._bulk(
            [
                (
                    str(item.incident_id),
                    item.incident_id,
                    _assign_operation(item.incident_id, item.assigned_user_id),
                )
                for item in payload.items
            ]
        )

    async def bulk_priority(
        self, payload: BulkIncidentPriorityRequest
    ) -> BulkOperationResponse:
        return await self._bulk(
            [
                (
                    str(item.incident_id),
                    item.incident_id,
                    _priority_operation(item.incident_id, item.priority.value),
                )
                for item in payload.items
            ]
        )

    async def _bulk(
        self, operations: list[tuple[str, uuid.UUID, BulkCallable]]
    ) -> BulkOperationResponse:
        if len(operations) > settings.supplier_api_max_bulk_items:
            raise HTTPException(
                413,
                detail={
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": (
                        "Najviše "
                        f"{settings.supplier_api_max_bulk_items} stavki po zahtevu"
                    ),
                },
            )
        results: list[BulkItemResult] = []
        seen: set[str] = set()
        for reference, resource_id, operation in operations:
            if reference in seen:
                results.append(
                    BulkItemResult(
                        input_reference=reference,
                        status="SKIPPED",
                        resource_id=resource_id,
                        error_code="DUPLICATE_INPUT",
                        message="Duplirana ulazna referenca je preskočena",
                    )
                )
                continue
            seen.add(reference)
            try:
                incident = await operation(SupplierIncidentService(self.session))
            except HTTPException as exc:
                await self.session.rollback()
                detail: dict[str, object] = (
                    exc.detail if isinstance(exc.detail, dict) else {}
                )
                results.append(
                    BulkItemResult(
                        input_reference=reference,
                        status="FAILED",
                        resource_id=resource_id,
                        error_code=str(detail.get("code", "OPERATION_FAILED")),
                        message=str(
                            detail.get("message", "Operacija nije uspela")
                        ),
                    )
                )
            else:
                results.append(
                    BulkItemResult(
                        input_reference=reference,
                        status="SUCCEEDED",
                        resource_id=incident.id,
                        resource_code=incident.incident_code,
                        message="Operacija je uspešno završena",
                    )
                )
        return BulkOperationResponse(
            requested_count=len(operations),
            succeeded_count=sum(row.status == "SUCCEEDED" for row in results),
            failed_count=sum(row.status == "FAILED" for row in results),
            skipped_count=sum(row.status == "SKIPPED" for row in results),
            results=results,
        )


__all__ = ["SupplierApiService"]
