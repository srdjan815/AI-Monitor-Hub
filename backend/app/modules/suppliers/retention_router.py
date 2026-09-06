from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.retention_schemas import (
    DataRetentionAnalysisRead,
    RetentionPolicyListRead,
    RetentionPolicyRead,
    RetentionPolicyWrite,
    RetentionRunRead,
)
from app.modules.suppliers.retention_service import (
    RetentionConflict,
    SupplierRetentionService,
)

router = APIRouter(prefix="/system/resources/data-retention", tags=["data-retention"])


@router.get("/policies", response_model=RetentionPolicyListRead)
async def list_policies(
    session: AsyncSession = Depends(get_db),
) -> RetentionPolicyListRead:
    return await SupplierRetentionService(session).policies()


@router.put("/policies/{source_id}", response_model=RetentionPolicyRead)
async def save_policy(
    source_id: uuid.UUID,
    payload: RetentionPolicyWrite,
    session: AsyncSession = Depends(get_db),
) -> RetentionPolicyRead:
    try:
        return await SupplierRetentionService(session).save_policy(source_id, payload)
    except RetentionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/policies/{source_id}/preview", response_model=DataRetentionAnalysisRead)
async def preview_policy(
    source_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> DataRetentionAnalysisRead:
    try:
        return await SupplierRetentionService(session).preview(source_id)
    except RetentionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs", response_model=list[RetentionRunRead])
async def list_runs(
    limit: int = Query(50, ge=1, le=200), session: AsyncSession = Depends(get_db)
) -> list[RetentionRunRead]:
    return await SupplierRetentionService(session).runs(limit)


__all__ = ["router"]
