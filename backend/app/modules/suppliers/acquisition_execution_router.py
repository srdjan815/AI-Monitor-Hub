from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.acquisition_schemas import (
    AcquisitionExecuteRequest,
    AcquisitionRetryRequest,
    AcquisitionRunRead,
)
from app.modules.suppliers.acquisition_service import SupplierAcquisitionService

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/acquisitions",
    tags=["supplier-acquisition-engine"],
)


@router.post(
    "/execute",
    response_model=AcquisitionRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Izvrši Acquisition sa konfigurisanog izvora",
    description=(
        "Sinhrono preuzima sadržaj kroz registrovani adapter, validira ga prema "
        "aktivnoj šemi i izvršava aktivna pravila mapiranja. Rezultat su staged "
        "zapisi, ne Snapshot i ne Catalog proizvodi. Idempotency ključ sprečava "
        "duplo izvršenje istog semantičkog zahteva."
    ),
)
async def execute_acquisition(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: AcquisitionExecuteRequest,
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunRead:
    run = await SupplierAcquisitionService(session).execute(
        supplier_id,
        source_id,
        idempotency_key=payload.idempotency_key,
    )
    return AcquisitionRunRead.model_validate(run)


@router.post(
    "/upload",
    response_model=AcquisitionRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload i izvršenje ručnog Acquisition-a",
    description=(
        "Prima sirovi sadržaj tela zahteva uz bezbedan display naziv fajla. "
        "Fajl dobija serversko ime, checksum i bezbednu artifact referencu. "
        "Originalni naziv se nikada ne koristi kao putanja."
    ),
)
async def upload_acquisition(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    request: Request,
    filename: str = Query(min_length=1, max_length=500),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
    ),
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunRead:
    run = await SupplierAcquisitionService(session).upload(
        supplier_id,
        source_id,
        content=await request.body(),
        filename=filename,
        content_type=request.headers.get("content-type"),
        idempotency_key=idempotency_key,
    )
    return AcquisitionRunRead.model_validate(run)


@router.post(
    "/{run_id}/cancel",
    response_model=AcquisitionRunRead,
    summary="Otkaži Acquisition Run",
    description=(
        "Otkazuje samo PENDING ili RUNNING izvršenje pre finalizacije staged "
        "rezultata. Terminalni run je nepromenljiv."
    ),
)
async def cancel_acquisition(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunRead:
    return AcquisitionRunRead.model_validate(
        await SupplierAcquisitionService(session).cancel(
            supplier_id,
            source_id,
            run_id,
        )
    )


@router.post(
    "/{run_id}/retry",
    response_model=AcquisitionRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ponovi terminalni Acquisition Run",
    description=(
        "Kreira novi run i ne menja original. Sačuvani artefakt se koristi kada "
        "postoji; u suprotnom se izvor ponovo poziva."
    ),
)
async def retry_acquisition(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: AcquisitionRetryRequest,
    session: AsyncSession = Depends(get_db),
) -> AcquisitionRunRead:
    return AcquisitionRunRead.model_validate(
        await SupplierAcquisitionService(session).retry(
            supplier_id,
            source_id,
            run_id,
            idempotency_key=payload.idempotency_key,
        )
    )


__all__ = ["router"]
