from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.system.maintenance_service import (
    CleanupConflict,
    SystemMaintenanceService,
)
from app.modules.system.artifact_archive_service import (
    ArchiveConfigurationError,
    ArtifactArchiveService,
)
from app.modules.system.resource_service import SystemResourceService
from app.modules.system.schemas import (
    CleanupAuditRead,
    CleanupExecuteRequest,
    CleanupPreviewRead,
    CleanupPreviewRequest,
    CleanupResultRead,
    SystemInventoryRead,
    ArchiveProcessRead,
    ArchiveSettingRead,
    ArchiveSettingWrite,
    ArchiveStatusRead,
    ArchiveTestRead,
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


@router.get(
    "/artifact-archive",
    response_model=ArchiveStatusRead,
    summary="Status arhiviranja cenovnika",
)
async def artifact_archive_status(
    session: AsyncSession = Depends(get_db),
) -> ArchiveStatusRead:
    return await ArtifactArchiveService(session).status()


@router.put(
    "/artifact-archive/setting",
    response_model=ArchiveSettingRead,
    summary="Podesi odredište arhive",
)
async def save_artifact_archive_setting(
    payload: ArchiveSettingWrite, session: AsyncSession = Depends(get_db)
) -> ArchiveSettingRead:
    try:
        return await ArtifactArchiveService(session).save_setting(payload)
    except ArchiveConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/artifact-archive/test",
    response_model=ArchiveTestRead,
    summary="Testiraj odredište arhive",
)
async def test_artifact_archive(
    session: AsyncSession = Depends(get_db),
) -> ArchiveTestRead:
    try:
        return await ArtifactArchiveService(session).test()
    except ArchiveConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/artifact-archive/process",
    response_model=ArchiveProcessRead,
    summary="Arhiviraj cenovnike na čekanju",
)
async def process_artifact_archive(
    limit: int = Query(25, ge=1, le=100), session: AsyncSession = Depends(get_db)
) -> ArchiveProcessRead:
    try:
        return await ArtifactArchiveService(session).process_pending(limit)
    except ArchiveConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


__all__ = ["router"]
