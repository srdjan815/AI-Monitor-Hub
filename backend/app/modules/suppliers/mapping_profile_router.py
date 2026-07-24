from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.enums import MappingProfileStatus
from app.modules.suppliers.mapping_profile_schemas import (
    MappingProfileAction,
    MappingProfileClone,
    MappingProfileCreate,
    MappingProfileListResponse,
    MappingProfileRead,
    MappingProfileUpdate,
)
from app.modules.suppliers.mapping_profile_service import (
    SupplierMappingProfileService,
)

router = APIRouter(
    prefix=(
        "/suppliers/{supplier_id}/sources/{source_id}/"
        "schema-profiles/{schema_profile_id}/mapping-profiles"
    ),
    tags=["supplier-mapping-profiles"],
)


@router.post(
    "",
    response_model=MappingProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj Mapping Profile",
    description=(
        "Kreira DRAFT verziju deklarativnog mapiranja aktivnog Schema Profile-a. "
        "Ne izvršava transformacije, uvoz niti upis u Catalog."
    ),
)
async def create_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    payload: MappingProfileCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    profile = await SupplierMappingProfileService(session).create_profile(
        supplier_id,
        source_id,
        schema_profile_id,
        payload,
    )
    response.headers["Location"] = (
        f"/api/v1/suppliers/{supplier_id}/sources/{source_id}/schema-profiles/"
        f"{schema_profile_id}/mapping-profiles/{profile.id}"
    )
    return MappingProfileRead.model_validate(profile)


@router.get(
    "",
    response_model=MappingProfileListResponse,
    summary="Prikaži Mapping Profile verzije",
    description="Vraća aktivne i istorijske verzije bez izvršavanja mapiranja.",
)
async def list_profiles(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    active_only: bool = Query(
        default=True,
        description="Kada je true, izostavlja soft-deleted verzije.",
    ),
    profile_status: MappingProfileStatus | None = Query(
        default=None,
        alias="status",
        description="Filtrira prema DRAFT, ACTIVE ili ARCHIVED statusu.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    session: AsyncSession = Depends(get_db),
) -> MappingProfileListResponse:
    rows, total = await SupplierMappingProfileService(session).list_profiles(
        supplier_id,
        source_id,
        schema_profile_id,
        active_only=active_only,
        status=profile_status.value if profile_status else None,
        limit=limit,
        offset=offset,
    )
    return MappingProfileListResponse(
        items=[MappingProfileRead.model_validate(row) for row in rows],
        total=total,
    )


@router.get(
    "/{mapping_profile_id}",
    response_model=MappingProfileRead,
    summary="Prikaži Mapping Profile",
    description="Vraća jednu verziju mapiranja iz zadatog Schema Profile-a.",
)
async def get_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    return MappingProfileRead.model_validate(
        await SupplierMappingProfileService(session).get_profile(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
        )
    )


@router.patch(
    "/{mapping_profile_id}",
    response_model=MappingProfileRead,
    summary="Izmeni DRAFT Mapping Profile",
    description="Menja samo DRAFT verziju uz optimističko zaključavanje.",
)
async def update_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    payload: MappingProfileUpdate,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    return MappingProfileRead.model_validate(
        await SupplierMappingProfileService(session).update_profile(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            payload,
        )
    )


@router.post(
    "/{mapping_profile_id}/clone",
    response_model=MappingProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kloniraj Mapping Profile",
    description="Kopira pravila u novu DRAFT verziju i čuva izvornu istoriju.",
)
async def clone_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    payload: MappingProfileClone,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    return MappingProfileRead.model_validate(
        await SupplierMappingProfileService(session).clone_profile(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            payload,
        )
    )


@router.post(
    "/{mapping_profile_id}/activate",
    response_model=MappingProfileRead,
    summary="Aktiviraj Mapping Profile verziju",
    description=(
        "Aktivira DRAFT verziju i arhivira prethodnu aktivnu verziju. Aktivacija "
        "je dozvoljena samo uz ACTIVE Schema Profile."
    ),
)
async def activate_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    payload: MappingProfileAction,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    return MappingProfileRead.model_validate(
        await SupplierMappingProfileService(session).activate_profile(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            payload,
        )
    )


@router.post(
    "/{mapping_profile_id}/archive",
    response_model=MappingProfileRead,
    summary="Arhiviraj Mapping Profile verziju",
    description="Čuva istorijsku verziju i prekida njen ACTIVE status.",
)
async def archive_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    payload: MappingProfileAction,
    session: AsyncSession = Depends(get_db),
) -> MappingProfileRead:
    return MappingProfileRead.model_validate(
        await SupplierMappingProfileService(session).archive_profile(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            payload,
        )
    )


@router.delete(
    "/{mapping_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete Mapping Profile",
    description="Sakriva verziju iz aktivnih lista, ali čuva profil i pravila.",
)
async def deactivate_profile(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierMappingProfileService(session).deactivate_profile(
        supplier_id,
        source_id,
        schema_profile_id,
        mapping_profile_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
