from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.schema_field_schemas import (
    SchemaFieldCreate,
    SchemaFieldListResponse,
    SchemaFieldRead,
    SchemaFieldUpdate,
)
from app.modules.suppliers.schema_field_service import SupplierSchemaFieldService

router = APIRouter(
    prefix=(
        "/suppliers/{supplier_id}/sources/{source_id}/"
        "schema-profiles/{profile_id}/fields"
    ),
    tags=["supplier-schema-profiles"],
)


@router.post(
    "",
    response_model=SchemaFieldRead,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaj Schema Field",
    description=(
        "Dodaje metadata opis ulaznog polja u DRAFT verziju. Putanja se samo "
        "čuva i ne izvršava se niti se koristi za parsiranje."
    ),
)
async def create_field(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SchemaFieldCreate,
    session: AsyncSession = Depends(get_db),
) -> SchemaFieldRead:
    return SchemaFieldRead.model_validate(
        await SupplierSchemaFieldService(session).create_field(
            supplier_id,
            source_id,
            profile_id,
            payload,
        )
    )


@router.get(
    "",
    response_model=SchemaFieldListResponse,
    summary="Prikaži Schema Fields",
    description="Vraća metadata polja deterministički sortirana prema poziciji.",
)
async def list_fields(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    active_only: bool = Query(
        default=True,
        description="Kada je true, prikazuje samo aktivna metadata polja.",
    ),
    session: AsyncSession = Depends(get_db),
) -> SchemaFieldListResponse:
    rows = await SupplierSchemaFieldService(session).list_fields(
        supplier_id,
        source_id,
        profile_id,
        active_only=active_only,
    )
    return SchemaFieldListResponse(
        items=[SchemaFieldRead.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.get(
    "/{field_id}",
    response_model=SchemaFieldRead,
    summary="Prikaži Schema Field",
    description="Vraća jedno polje samo iz zadate Schema Profile verzije.",
)
async def get_field(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    field_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SchemaFieldRead:
    return SchemaFieldRead.model_validate(
        await SupplierSchemaFieldService(session).get_field(
            supplier_id,
            source_id,
            profile_id,
            field_id,
        )
    )


@router.patch(
    "/{field_id}",
    response_model=SchemaFieldRead,
    summary="Izmeni Schema Field",
    description=(
        "Menja metadata polja isključivo u DRAFT verziji uz optimističko "
        "zaključavanje. Ne predstavlja mapiranje ili transformaciju."
    ),
)
async def update_field(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: SchemaFieldUpdate,
    session: AsyncSession = Depends(get_db),
) -> SchemaFieldRead:
    return SchemaFieldRead.model_validate(
        await SupplierSchemaFieldService(session).update_field(
            supplier_id,
            source_id,
            profile_id,
            field_id,
            payload,
        )
    )


@router.delete(
    "/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete Schema Field",
    description="Arhivira metadata polje samo u DRAFT verziji profila.",
)
async def deactivate_field(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    field_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierSchemaFieldService(session).deactivate_field(
        supplier_id,
        source_id,
        profile_id,
        field_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
