from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.delta_query_service import SupplierDeltaQueryService
from app.modules.suppliers.delta_schemas import (
    DeltaCalculate, DeltaCompatibility, DeltaCurrentCalculate, DeltaFieldList,
    DeltaFieldRead, DeltaItemList, DeltaItemRead, DeltaRunList, DeltaRunRead,
)
from app.modules.suppliers.delta_service import SupplierDeltaService
from app.modules.suppliers.enums import DeltaChangeType

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/deltas",
    tags=["supplier-delta-engine"],
)


@router.post("", response_model=DeltaRunRead, status_code=status.HTTP_201_CREATED, summary="Izračunaj Delta Run", description="Poredi dva kompatibilna immutable READY Snapshot-a. Rezultat beleži činjenice i ne menja Catalog niti Inventory.")
async def calculate(supplier_id: uuid.UUID, source_id: uuid.UUID, payload: DeltaCalculate, session: AsyncSession = Depends(get_db)) -> DeltaRunRead:
    run = await SupplierDeltaService(session).calculate(supplier_id, source_id, payload.previous_snapshot_id, payload.current_snapshot_id, payload.idempotency_key)
    return DeltaRunRead.model_validate(run)


@router.post("/from-current", response_model=DeltaRunRead, status_code=status.HTTP_201_CREATED, summary="Izračunaj prema prethodnom Snapshot-u", description="Bira najbliži stariji READY Snapshot istog dobavljača i izvora.")
async def calculate_previous(supplier_id: uuid.UUID, source_id: uuid.UUID, payload: DeltaCurrentCalculate, session: AsyncSession = Depends(get_db)) -> DeltaRunRead:
    return DeltaRunRead.model_validate(await SupplierDeltaService(session).calculate_previous(supplier_id, source_id, payload.current_snapshot_id, payload.idempotency_key))


@router.get("/compatibility", response_model=DeltaCompatibility, summary="Proveri kompatibilnost", description="Proverava Snapshot par bez pokretanja poređenja. ARCHIVED payload zahteva eksplicitni restore.")
async def compatibility(supplier_id: uuid.UUID, source_id: uuid.UUID, previous_snapshot_id: uuid.UUID, current_snapshot_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> DeltaCompatibility:
    await SupplierDeltaService(session).compatibility(supplier_id, source_id, previous_snapshot_id, current_snapshot_id)
    return DeltaCompatibility(compatible=True, code="DELTA_COMPATIBLE", message="Snapshot-i su kompatibilni", previous_snapshot_id=previous_snapshot_id, current_snapshot_id=current_snapshot_id)


@router.get("", response_model=DeltaRunList, summary="Prikaži Delta Run-ove", description="Vraća ograničenu listu bez potpunih Snapshot payload-a.")
async def list_runs(supplier_id: uuid.UUID, source_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> DeltaRunList:
    rows, total = await SupplierDeltaQueryService(session).list_runs(supplier_id, source_id, limit=limit, offset=offset)
    return DeltaRunList(items=[DeltaRunRead.model_validate(row) for row in rows], total=total)


@router.get("/{run_id}", response_model=DeltaRunRead, summary="Prikaži Delta Run", description="Vraća lifecycle, sažetak, statistiku i anomaly signale. Signal nije Incident.")
@router.get("/{run_id}/summary", response_model=DeltaRunRead, summary="Prikaži Delta sažetak", description="Vraća usaglašene zbirne rezultate i comparison version.")
async def get_run(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> DeltaRunRead:
    return DeltaRunRead.model_validate(await SupplierDeltaQueryService(session).get(supplier_id, source_id, run_id))


@router.get("/{run_id}/items", response_model=DeltaItemList, summary="Prikaži promenjene stavke", description="ADDED, REMOVED i MODIFIED stavke bez kopiranja kompletnog mapped_data payload-a.")
async def list_items(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, change_type: DeltaChangeType | None = None, has_price_change: bool | None = None, has_stock_change: bool | None = None, has_image_change: bool | None = None, has_identifier_change: bool | None = None, anomaly_flag: str | None = Query(default=None, max_length=100), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> DeltaItemList:
    rows, total = await SupplierDeltaQueryService(session).items(supplier_id, source_id, run_id, change_type=change_type.value if change_type else None, price=has_price_change, stock=has_stock_change, image=has_image_change, identifier=has_identifier_change, anomaly_flag=anomaly_flag, limit=limit, offset=offset)
    return DeltaItemList(items=[DeltaItemRead.model_validate(row) for row in rows], total=total)


@router.get("/{run_id}/items/{item_id}", response_model=DeltaItemRead, summary="Prikaži Delta stavku", description="Vraća klasifikaciju i reference na originalne Snapshot Items.")
async def get_item(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> DeltaItemRead:
    return DeltaItemRead.model_validate(await SupplierDeltaQueryService(session).item(supplier_id, source_id, run_id, item_id))


@router.get("/{run_id}/items/{item_id}/field-changes", response_model=DeltaFieldList, summary="Prikaži promene polja", description="Vraća hash, ograničen pregled i numeričku promenu; dugi tekst ostaje u Snapshot Item-u.")
async def field_changes(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, item_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> DeltaFieldList:
    service = SupplierDeltaQueryService(session)
    await service.item(supplier_id, source_id, run_id, item_id)
    rows, total = await service.repository.field_changes(item_id, limit=limit, offset=offset)
    return DeltaFieldList(items=[DeltaFieldRead.model_validate(row) for row in rows], total=total)


@router.post("/{run_id}/cancel", response_model=DeltaRunRead, summary="Otkaži Delta Run", description="Otkaži PENDING ili RUNNING pokušaj pre finalizacije.")
async def cancel(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> DeltaRunRead:
    run = await SupplierDeltaQueryService(session).get(supplier_id, source_id, run_id)
    return DeltaRunRead.model_validate(await SupplierDeltaService(session).cancel(run.id))


@router.post("/{run_id}/retry", response_model=DeltaRunRead, status_code=status.HTTP_201_CREATED, summary="Ponovi neuspešno poređenje", description="Kreira novi Delta Run; terminalni pokušaj se ne resetuje.")
async def retry(supplier_id: uuid.UUID, source_id: uuid.UUID, run_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> DeltaRunRead:
    run = await SupplierDeltaQueryService(session).get(supplier_id, source_id, run_id)
    if run.status not in {"FAILED", "CANCELLED"}:
        from app.modules.suppliers.errors import supplier_error
        supplier_error(409, "delta_retry_ineligible", "Samo FAILED ili CANCELLED pokušaj može biti ponovljen")
    return DeltaRunRead.model_validate(await SupplierDeltaService(session).calculate(supplier_id, source_id, run.previous_snapshot_id, run.current_snapshot_id))


__all__ = ["router"]
