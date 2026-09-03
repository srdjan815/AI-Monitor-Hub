from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.contact_service import SupplierContactService
from app.modules.suppliers.enums import SupplierContactType
from app.modules.suppliers.schemas import (
    SupplierContactCreate,
    SupplierContactListResponse,
    SupplierContactRead,
    SupplierContactUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["supplier-administration"])


@router.post(
    "/{supplier_id}/contacts",
    response_model=SupplierContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaj kontakt dobavljača",
    description=(
        "Dodaje kontakt sa najmanje jednim kanalom: email ili telefon. Samo jedan "
        "aktivan glavni kontakt može postojati za svaku vrstu kontakta."
    ),
)
async def create_contact(
    supplier_id: uuid.UUID,
    payload: SupplierContactCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> SupplierContactRead:
    contact = await SupplierContactService(session).create_contact(
        supplier_id,
        payload,
    )
    response.headers["Location"] = (
        f"/api/v1/suppliers/{supplier_id}/contacts/{contact.id}"
    )
    return SupplierContactRead.model_validate(contact)


@router.get(
    "/{supplier_id}/contacts",
    response_model=SupplierContactListResponse,
    summary="Prikaži kontakte dobavljača",
    description="Vraća filtriranu i deterministički sortiranu listu kontakata.",
)
async def list_contacts(
    supplier_id: uuid.UUID,
    active_only: bool = Query(
        default=True,
        description="Kada je true, prikazuje samo aktivne kontakte.",
    ),
    contact_type: SupplierContactType | None = Query(
        default=None,
        description="Ograničava rezultate na izabranu vrstu kontakta.",
    ),
    is_primary: bool | None = Query(
        default=None,
        description="Filtrira glavne ili sporedne kontakte.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Najveći broj kontakata u jednoj stranici.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=MAX_LEGACY_OFFSET,
        description="Broj preskočenih kontakata.",
    ),
    session: AsyncSession = Depends(get_db),
) -> SupplierContactListResponse:
    rows, total = await SupplierContactService(session).list_contacts(
        supplier_id,
        active_only=active_only,
        contact_type=contact_type.value if contact_type is not None else None,
        is_primary=is_primary,
        limit=limit,
        offset=offset,
    )
    return SupplierContactListResponse(
        items=[SupplierContactRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{supplier_id}/contacts/{contact_id}",
    response_model=SupplierContactRead,
    summary="Prikaži kontakt dobavljača",
    description="Vraća kontakt samo ako pripada dobavljaču iz putanje.",
)
async def get_contact(
    supplier_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SupplierContactRead:
    return SupplierContactRead.model_validate(
        await SupplierContactService(session).get_contact(supplier_id, contact_id)
    )


@router.patch(
    "/{supplier_id}/contacts/{contact_id}",
    response_model=SupplierContactRead,
    summary="Izmeni kontakt dobavljača",
    description=(
        "Menja samo prosleđena polja kontakta uz obaveznu očekivanu version vrednost."
    ),
)
async def update_contact(
    supplier_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: SupplierContactUpdate,
    session: AsyncSession = Depends(get_db),
) -> SupplierContactRead:
    return SupplierContactRead.model_validate(
        await SupplierContactService(session).update_contact(
            supplier_id,
            contact_id,
            payload,
        )
    )


@router.delete(
    "/{supplier_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deaktiviraj kontakt dobavljača",
    description="Soft delete kontakta bez fizičkog brisanja istorijskih podataka.",
)
async def deactivate_contact(
    supplier_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierContactService(session).deactivate_contact(
        supplier_id,
        contact_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
