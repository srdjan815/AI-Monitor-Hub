from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppliers.incident_contracts import INCIDENT_TYPES, SOURCE_DOMAINS
from app.modules.suppliers.incident_models import SupplierIncidentRule
from app.modules.suppliers.incident_repository import SupplierIncidentRepository
from app.modules.suppliers.incident_schemas import RuleCreate, RuleUpdate
from app.modules.suppliers.errors import supplier_error


class SupplierIncidentRuleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierIncidentRepository(session)

    async def create(self, payload: RuleCreate) -> SupplierIncidentRule:
        if (
            payload.source_domain not in SOURCE_DOMAINS
            or payload.incident_type not in INCIDENT_TYPES
        ):
            supplier_error(
                422,
                "incident_rule_classification_invalid",
                "Rule klasifikacija nije validna",
            )
        if (
            payload.supplier_id
            and await self.repository.supplier(payload.supplier_id) is None
        ):
            supplier_error(
                404,
                "supplier_not_found",
                "Dobavljač nije pronađen",
            )
        if (
            payload.source_connection_id
            and await self.repository.source(payload.source_connection_id) is None
        ):
            supplier_error(
                404,
                "supplier_source_not_found",
                "Izvor nije pronađen",
            )
        rule = SupplierIncidentRule(
            **payload.model_dump(),
            minimum_severity="INFO",
            enabled=True,
            is_active=True,
        )
        try:
            await self.repository.add_rule(rule)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            supplier_error(
                409,
                "incident_rule_code_exists",
                "Rule code već postoji",
            )
        await self.session.refresh(rule)
        return rule

    async def update(
        self,
        rule_id: uuid.UUID,
        payload: RuleUpdate,
    ) -> SupplierIncidentRule:
        rule = await self.repository.get_rule(rule_id)
        if rule is None:
            supplier_error(
                404,
                "incident_rule_not_found",
                "Incident Rule nije pronađen",
            )
        await self.repository.mutate_rule(
            rule,
            payload.model_dump(exclude_none=True),
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def deactivate(self, rule_id: uuid.UUID) -> SupplierIncidentRule:
        rule = await self.repository.get_rule(rule_id)
        if rule is None:
            supplier_error(
                404,
                "incident_rule_not_found",
                "Incident Rule nije pronađen",
            )
        await self.repository.mutate_rule(
            rule,
            {"is_active": False, "enabled": False},
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return rule


__all__ = ["SupplierIncidentRuleService"]
