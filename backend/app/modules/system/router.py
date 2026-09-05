from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.system.maintenance_service import (
    CleanupConflict,
    SystemMaintenanceService,
)
from app.modules.system.resource_service import SystemResourceService
from app.modules.system.schemas import (
    CleanupAuditRead,
    CleanupExecuteRequest,
    CleanupPreviewRead,
    CleanupPreviewRequest,
    CleanupResultRead,
    SystemInventoryRead,
)

router = APIRouter(prefix="/system/resources", tags=["system-resources"])


@router.get("", response_model=SystemInventoryRead, summary="Pregled resursa sistema")
async def inventory(session: AsyncSession = Depends(get_db)) -> SystemInventoryRead:
    return await SystemResourceService(session).inventory()


@router.post(
    "/cleanup/preview",
    response_model=CleanupPreviewRead,
    summary="Pregled bezbednog čišćenja",
)
async def preview_cleanup(
    payload: CleanupPreviewRequest,
    session: AsyncSession = Depends(get_db),
) -> CleanupPreviewRead:
    try:
        return SystemMaintenanceService(session).preview(payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/cleanup/execute",
    response_model=CleanupResultRead,
    summary="Izvrši potvrđeno bezbedno čišćenje",
)
async def execute_cleanup(
    payload: CleanupExecuteRequest,
    session: AsyncSession = Depends(get_db),
) -> CleanupResultRead:
    try:
        return await SystemMaintenanceService(session).execute(payload)
    except (CleanupConflict, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get(
    "/cleanup/audit",
    response_model=list[CleanupAuditRead],
    summary="Audit istorija čišćenja",
)
async def cleanup_audit(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> list[CleanupAuditRead]:
    return await SystemMaintenanceService(session).audit(limit)


__all__ = ["router"]
