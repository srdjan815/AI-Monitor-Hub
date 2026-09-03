from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.mapping_profile_models import SupplierMappingRule
from app.modules.suppliers.mapping_rule_schemas import (
    MappingRuleCreate,
    MappingRuleUpdate,
)
from app.modules.suppliers.mapping_service_support import (
    SupplierMappingServiceSupport,
)


class SupplierMappingRuleService(SupplierMappingServiceSupport):
    """Transaction owner for DRAFT Mapping Rule metadata."""

    async def list_rules(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        *,
        active_only: bool = True,
    ) -> list[SupplierMappingRule]:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        await self._profile(schema_profile_id, mapping_profile_id)
        return await self.repository.list_rules(
            mapping_profile_id,
            active_only=active_only,
        )

    async def get_rule(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> SupplierMappingRule:
        await self._lineage(supplier_id, source_id, schema_profile_id)
        await self._profile(schema_profile_id, mapping_profile_id)
        rule = await self.repository.get_rule(mapping_profile_id, rule_id)
        if rule is None:
            supplier_error(404, "mapping_rule_not_found", "Mapping Rule nije pronađen")
        return rule

    async def create_rule(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        data: MappingRuleCreate,
    ) -> SupplierMappingRule:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._draft(profile)
        await self._field(schema_profile_id, data.schema_field_id)
        await self._configured_fields(schema_profile_id, data)
        values = self._values(data)
        await self._conflicts(mapping_profile_id, values)
        rule = SupplierMappingRule(mapping_profile_id=mapping_profile_id, **values)
        try:
            await self.repository.add(rule)
            await self.repository.mutate(
                profile,
                {
                    "rule_count": profile.rule_count + 1,
                    "optimistic_version": profile.optimistic_version + 1,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(rule)
        return rule

    async def update_rule(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: MappingRuleUpdate,
    ) -> SupplierMappingRule:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._draft(profile)
        rule = await self.repository.get_rule(
            mapping_profile_id,
            rule_id,
            for_update=True,
        )
        if rule is None:
            supplier_error(404, "mapping_rule_not_found", "Mapping Rule nije pronađen")
        if not rule.is_active:
            supplier_error(409, "mapping_rule_inactive", "Mapping Rule je arhiviran")
        if rule.optimistic_version != data.optimistic_version:
            supplier_error(
                409,
                "mapping_rule_version_conflict",
                "Mapping Rule je u međuvremenu izmenjen",
            )
        supplied = data.model_dump(
            exclude_unset=True,
            exclude={"optimistic_version"},
        )
        current = {name: getattr(rule, name) for name in MappingRuleCreate.model_fields}
        current.update(supplied)
        validated = MappingRuleCreate.model_validate(current)
        await self._field(schema_profile_id, validated.schema_field_id)
        await self._configured_fields(schema_profile_id, validated)
        values = self._values(validated)
        await self._conflicts(mapping_profile_id, values, rule.id)
        changes = {
            key: value for key, value in values.items() if getattr(rule, key) != value
        }
        if changes:
            changes["optimistic_version"] = rule.optimistic_version + 1
        try:
            if changes:
                await self.repository.mutate(rule, changes)
                await self.repository.mutate(
                    profile,
                    {"optimistic_version": profile.optimistic_version + 1},
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            self._integrity(exc)
        except StaleDataError:
            await self.session.rollback()
            self._stale_rule()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(rule)
        return rule

    async def deactivate_rule(
        self,
        supplier_id: uuid.UUID,
        source_id: uuid.UUID,
        schema_profile_id: uuid.UUID,
        mapping_profile_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> None:
        await self._usable_schema(supplier_id, source_id, schema_profile_id)
        profile = await self._profile(
            schema_profile_id,
            mapping_profile_id,
            for_update=True,
        )
        self._draft(profile)
        rule = await self.repository.get_rule(
            mapping_profile_id,
            rule_id,
            for_update=True,
        )
        if rule is None:
            supplier_error(404, "mapping_rule_not_found", "Mapping Rule nije pronađen")
        if not rule.is_active:
            return
        try:
            await self.repository.mutate(
                rule,
                {
                    "is_active": False,
                    "optimistic_version": rule.optimistic_version + 1,
                },
            )
            await self.repository.mutate(
                profile,
                {
                    "rule_count": profile.rule_count - 1,
                    "optimistic_version": profile.optimistic_version + 1,
                },
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            self._stale_rule()
        except Exception:
            await self.session.rollback()
            raise

    async def _field(
        self,
        schema_profile_id: uuid.UUID,
        field_id: uuid.UUID,
    ) -> None:
        field = await self.schemas.get_field(schema_profile_id, field_id)
        if field is None:
            supplier_error(
                404,
                "mapping_rule_schema_field_not_found",
                "Schema Field ne pripada povezanom Schema Profile-u",
            )
        if not field.is_active:
            supplier_error(
                409,
                "mapping_rule_schema_field_inactive",
                "Neaktivni Schema Field se ne može mapirati",
            )

    async def _conflicts(
        self,
        mapping_profile_id: uuid.UUID,
        values: dict[str, object],
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        conflicts = await self.repository.rule_conflicts(
            mapping_profile_id,
            schema_field_id=cast(uuid.UUID, values["schema_field_id"]),
            target_attribute=str(values["target_attribute"]),
            priority=cast(int, values["priority"]),
            exclude_id=exclude_id,
        )
        errors = {
            "field": ("mapping_rule_field_conflict", "Schema Field je već mapiran"),
            "priority": ("mapping_rule_priority_conflict", "Prioritet već postoji"),
            "target": ("mapping_rule_target_conflict", "Ciljni atribut je već mapiran"),
        }
        if conflicts:
            code, message = errors[sorted(conflicts)[0]]
            supplier_error(409, code, message)

    async def _configured_fields(
        self,
        schema_profile_id: uuid.UUID,
        data: MappingRuleCreate,
    ) -> None:
        config = data.transformation_config or {}
        raw_ids = config.get("field_ids")
        if data.transformation_type.value != "CONCAT" or raw_ids is None:
            return
        if not isinstance(raw_ids, list) or not raw_ids:
            supplier_error(
                422,
                "mapping_concat_fields_invalid",
                "Sastavljeno mapiranje zahteva najmanje jedno izvorno polje",
            )
        parsed: list[uuid.UUID] = []
        try:
            parsed = [uuid.UUID(str(value)) for value in raw_ids]
        except (TypeError, ValueError):
            supplier_error(
                422,
                "mapping_concat_fields_invalid",
                "Sastavljeno mapiranje sadrži neispravno izvorno polje",
            )
        if len(parsed) != len(set(parsed)):
            supplier_error(
                422,
                "mapping_concat_fields_duplicate",
                "Isto izvorno polje ne može biti dodato više puta",
            )
        for field_id in parsed:
            await self._field(schema_profile_id, field_id)

    @staticmethod
    def _values(data: MappingRuleCreate) -> dict[str, object]:
        values = data.model_dump()
        values["target_attribute"] = data.target_attribute.strip().lower()
        values["transformation_type"] = data.transformation_type.value
        return values

    @staticmethod
    def _stale_rule() -> None:
        supplier_error(
            409,
            "mapping_rule_version_conflict",
            "Mapping Rule je u međuvremenu izmenjen",
        )


__all__ = ["SupplierMappingRuleService"]
