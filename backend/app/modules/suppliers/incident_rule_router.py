from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limits import MAX_LEGACY_OFFSET
from app.db.session import get_db
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.incident_query_service import SupplierIncidentQueryService
from app.modules.suppliers.incident_schemas import RuleCreate, RuleList, RuleRead, RuleUpdate
from app.modules.suppliers.incident_rule_service import SupplierIncidentRuleService

router = APIRouter(prefix="/supplier-incident-rules", tags=["supplier-incident-rules"])


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED, summary="Kreiraj Incident Rule", description="Kreira tipizirano pravilo bez eval, exec ili skripti.")
async def create_rule(payload: RuleCreate, session: AsyncSession = Depends(get_db)) -> RuleRead:
    return RuleRead.model_validate(await SupplierIncidentRuleService(session).create(payload))


@router.get("", response_model=RuleList, summary="Prikaži Incident Rules", description="Vraća ograničenu listu aktivnih globalnih i scoped pravila.")
async def list_rules(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0, le=MAX_LEGACY_OFFSET), session: AsyncSession = Depends(get_db)) -> RuleList:
    rows, total = await SupplierIncidentQueryService(session).repository.list_rules(limit=limit, offset=offset)
    return RuleList(items=[RuleRead.model_validate(row) for row in rows], total=total)


@router.get("/{rule_id}", response_model=RuleRead, summary="Prikaži Incident Rule", description="Vraća tipiziranu klasifikaciju, pragove i scope.")
async def get_rule(rule_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> RuleRead:
    rule = await SupplierIncidentQueryService(session).repository.get_rule(rule_id)
    if rule is None:
        supplier_error(404, "incident_rule_not_found", "Incident Rule nije pronađen")
    return RuleRead.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleRead, summary="Ažuriraj Incident Rule", description="Menja samo enabled, pragove i resulting klasifikaciju.")
async def update_rule(rule_id: uuid.UUID, payload: RuleUpdate, session: AsyncSession = Depends(get_db)) -> RuleRead:
    return RuleRead.model_validate(await SupplierIncidentRuleService(session).update(rule_id, payload))


@router.delete("/{rule_id}", response_model=RuleRead, summary="Deaktiviraj Incident Rule", description="Soft-deaktivira pravilo bez brisanja istorijskih Incidenata.")
async def deactivate_rule(rule_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> RuleRead:
    return RuleRead.model_validate(await SupplierIncidentRuleService(session).deactivate(rule_id))


__all__ = ["router"]
