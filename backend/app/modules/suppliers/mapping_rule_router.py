from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.suppliers.mapping_rule_schemas import (
    MappingRuleCreate,
    MappingRuleListResponse,
    MappingRuleRead,
    MappingRuleUpdate,
)
from app.modules.suppliers.mapping_rule_service import SupplierMappingRuleService

router = APIRouter(
    prefix=(
        "/suppliers/{supplier_id}/sources/{source_id}/schema-profiles/"
        "{schema_profile_id}/mapping-profiles/{mapping_profile_id}/rules"
    ),
    tags=["supplier-mapping-profiles"],
)


@router.post(
    "",
    response_model=MappingRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaj Mapping Rule",
    description=(
        "Povezuje postojeći Schema Field sa logičkim Catalog atributom. "
        "Transformacija i validacija se samo čuvaju, nikada ne izvršavaju."
    ),
)
async def create_rule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    payload: MappingRuleCreate,
    session: AsyncSession = Depends(get_db),
) -> MappingRuleRead:
    return MappingRuleRead.model_validate(
        await SupplierMappingRuleService(session).create_rule(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            payload,
        )
    )


@router.get(
    "",
    response_model=MappingRuleListResponse,
    summary="Prikaži Mapping Rules",
    description="Vraća pravila deterministički sortirana prema prioritetu.",
)
async def list_rules(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    active_only: bool = Query(
        default=True,
        description="Kada je true, prikazuje samo aktivna pravila.",
    ),
    session: AsyncSession = Depends(get_db),
) -> MappingRuleListResponse:
    rows = await SupplierMappingRuleService(session).list_rules(
        supplier_id,
        source_id,
        schema_profile_id,
        mapping_profile_id,
        active_only=active_only,
    )
    return MappingRuleListResponse(
        items=[MappingRuleRead.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.get(
    "/{rule_id}",
    response_model=MappingRuleRead,
    summary="Prikaži Mapping Rule",
    description="Vraća jedno pravilo samo iz zadate verzije mapiranja.",
)
async def get_rule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> MappingRuleRead:
    return MappingRuleRead.model_validate(
        await SupplierMappingRuleService(session).get_rule(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            rule_id,
        )
    )


@router.patch(
    "/{rule_id}",
    response_model=MappingRuleRead,
    summary="Izmeni Mapping Rule",
    description="Parcijalno menja pravilo samo u DRAFT Mapping Profile verziji.",
)
async def update_rule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: MappingRuleUpdate,
    session: AsyncSession = Depends(get_db),
) -> MappingRuleRead:
    return MappingRuleRead.model_validate(
        await SupplierMappingRuleService(session).update_rule(
            supplier_id,
            source_id,
            schema_profile_id,
            mapping_profile_id,
            rule_id,
            payload,
        )
    )


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete Mapping Rule",
    description="Arhivira pravilo samo u DRAFT verziji Mapping Profile-a.",
)
async def deactivate_rule(
    supplier_id: uuid.UUID,
    source_id: uuid.UUID,
    schema_profile_id: uuid.UUID,
    mapping_profile_id: uuid.UUID,
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    await SupplierMappingRuleService(session).deactivate_rule(
        supplier_id,
        source_id,
        schema_profile_id,
        mapping_profile_id,
        rule_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
