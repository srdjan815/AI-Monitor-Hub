from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.enums import SchemaProfileStatus
from app.modules.suppliers.schema_profile_schemas import (
    SchemaProfileAction,
    SchemaProfileClone,
    SchemaProfileCreate,
    SchemaProfileListResponse,
    SchemaProfileRead,
    SchemaProfileUpdate,
)
from app.modules.suppliers.schema_profile_service import SupplierSchemaProfileService

router = APIRouter(
    prefix="/suppliers/{supplier_id}/sources/{source_id}/schema-profiles",
    tags=["supplier-schema-profiles"],
)


@router.post(
    "",
    response_model=SchemaProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj Schema Profile",
    description=(
        "Kreira DRAFT opis strukture izvora. Profil ne sadrži dobavljačke podatke "
        "i ne pokreće parsiranje, uvoz niti automatsko otkrivanje šeme."
    ),
)
async def create_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SchemaProfileCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    profile = await SupplierSchemaProfileService(session).create_profile(
        supplier_id,
        source_id,
        payload,
    )
    response.headers["Location"] = (
        f"/api/v1/suppliers/{supplier_id}/sources/{source_id}/"
        f"schema-profiles/{profile.id}"
    )
    return SchemaProfileRead.model_validate(profile)


@router.get(
    "",
    response_model=SchemaProfileListResponse,
    summary="Prikaži Schema Profile verzije",
    description=(
        "Prikazuje aktuelne i istorijske verzije strukture. Istorijske verzije "
        "ostaju čitljive i nikada se ne menjaju."
    ),
)
async def list_profiles(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    active_only: bool = Query(
        default=True,
        description="Kada je true, izostavlja soft-deleted verzije.",
    ),
    profile_status: SchemaProfileStatus | None = Query(
        default=None,
        alias="status",
        description="Filtrira verzije prema DRAFT, ACTIVE ili ARCHIVED statusu.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileListResponse:
    rows, total = await SupplierSchemaProfileService(session).list_profiles(
        supplier_id,
        source_id,
        active_only=active_only,
        status=profile_status.value if profile_status is not None else None,
        limit=limit,
        offset=offset,
    )
    return SchemaProfileListResponse(
        items=[SchemaProfileRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{profile_id}",
    response_model=SchemaProfileRead,
    summary="Prikaži Schema Profile verziju",
    description="Vraća tačno jednu verziju koja pripada Source Connection-u.",
)
async def get_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    return SchemaProfileRead.model_validate(
        await SupplierSchemaProfileService(session).get_profile(
            supplier_id,
            source_id,
            profile_id,
        )
    )


@router.patch(
    "/{profile_id}",
    response_model=SchemaProfileRead,
    summary="Izmeni DRAFT profil",
    description=(
        "Menja samo administrativne podatke DRAFT verzije uz optimističko "
        "zaključavanje. ACTIVE i ARCHIVED verzije su nepromenljive."
    ),
)
async def update_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SchemaProfileUpdate,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    return SchemaProfileRead.model_validate(
        await SupplierSchemaProfileService(session).update_profile(
            supplier_id,
            source_id,
            profile_id,
            payload,
        )
    )


@router.post(
    "/{profile_id}/clone",
    response_model=SchemaProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kloniraj verziju",
    description=(
        "Kopira profil i njegova metadata polja u novu DRAFT verziju. "
        "Izvorna istorijska verzija ostaje nepromenjena."
    ),
)
async def clone_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SchemaProfileClone,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    return SchemaProfileRead.model_validate(
        await SupplierSchemaProfileService(session).clone_profile(
            supplier_id,
            source_id,
            profile_id,
            payload,
        )
    )


@router.post(
    "/{profile_id}/activate",
    response_model=SchemaProfileRead,
    summary="Aktiviraj Schema Profile verziju",
    description=(
        "Aktivira proverenu DRAFT verziju i arhivira prethodnu aktivnu verziju. "
        "Jedan Source Connection može imati samo jednu ACTIVE verziju."
    ),
)
async def activate_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SchemaProfileAction,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    return SchemaProfileRead.model_validate(
        await SupplierSchemaProfileService(session).activate_profile(
            supplier_id,
            source_id,
            profile_id,
            payload,
        )
    )


@router.post(
    "/{profile_id}/archive",
    response_model=SchemaProfileRead,
    summary="Arhiviraj verziju",
    description="Postavlja verziju u ARCHIVED status bez brisanja istorije.",
)
async def archive_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: SchemaProfileAction,
    session: AsyncSession = Depends(get_db),
) -> SchemaProfileRead:
    return SchemaProfileRead.model_validate(
        await SupplierSchemaProfileService(session).archive_profile(
            supplier_id,
            source_id,
            profile_id,
            payload,
        )
    )


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete Schema Profile verziju",
    description="Sakriva zapis iz aktivnih lista, ali čuva istorijsku verziju i polja.",
)
async def deactivate_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    profile_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierSchemaProfileService(session).deactivate_profile(
        supplier_id,
        source_id,
        profile_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
