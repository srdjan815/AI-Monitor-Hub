from __future__ import annotations

import uuid

import regex as timeout_regex
from fastapi import HTTPException

from app.modules.catalog.attribute_models import (
    AttributeNormalizationRule,
    AttributeOption,
    AttributeOptionAlias,
)
from app.modules.catalog.models import (
    AttributeDefinition,
)
from app.modules.catalog.schemas.product_attributes import (
    AttributeAliasCreate,
    AttributeOptionCreate,
    AttributeOptionUpdate,
    NormalizationRuleCreate,
    NormalizationRuleUpdate,
)

from app.modules.catalog.attribute_service_support import ProductAttributeServiceSupport


class AttributeOptionService(ProductAttributeServiceSupport):
    @staticmethod
    def _validate_rule_pattern(rule_type: object, pattern: str) -> None:
        value = getattr(rule_type, "value", rule_type)
        if value not in {"REGEX", "UNIT", "CUSTOM_TEMPLATE"}:
            return
        try:
            timeout_regex.compile(pattern)
        except timeout_regex.error as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid regex: {exc}"
            ) from exc

    async def create_option(
        self, attribute_id: uuid.UUID, data: AttributeOptionCreate
    ) -> AttributeOption:
        definition = await self._required(
            AttributeDefinition, attribute_id, "Attribute definition"
        )
        if definition.data_type not in {"ENUM", "MULTI_ENUM", "SELECT", "MULTISELECT"}:
            raise HTTPException(
                status_code=409, detail="Options require an enum attribute"
            )
        option = AttributeOption(
            attribute_definition_id=attribute_id,
            canonical_value=data.canonical_value.strip(),
            display_value=(data.display_value or data.canonical_value).strip(),
            sort_order=data.sort_order,
            option_metadata=data.metadata,
        )
        await self.repository.add(option)
        for alias in data.aliases:
            await self._create_alias(option, alias)
        await self._event("ATTRIBUTE_OPTION", option.id, "CREATED")
        return await self._commit(option)

    async def update_option(
        self, option_id: uuid.UUID, data: AttributeOptionUpdate
    ) -> AttributeOption:
        option = await self._required(AttributeOption, option_id, "Attribute option")
        changes = data.model_dump(exclude_unset=True)
        if "metadata" in changes:
            changes["option_metadata"] = changes.pop("metadata")
        await self.repository.mutate(option, changes)
        await self._event("ATTRIBUTE_OPTION", option.id, "UPDATED")
        return await self._commit(option)

    async def deactivate_option(self, option_id: uuid.UUID) -> None:
        option = await self._required(AttributeOption, option_id, "Attribute option")
        await self.repository.mutate(option, {"is_active": False})
        await self._event("ATTRIBUTE_OPTION", option.id, "DEACTIVATED")
        await self._commit()

    async def _create_alias(
        self, option: AttributeOption, alias: str
    ) -> AttributeOptionAlias:
        normalized = self._alias_key(alias)
        if await self.repository.alias_by_normalized(
            option.attribute_definition_id, normalized
        ):
            raise HTTPException(status_code=409, detail="Alias already exists")
        return await self.repository.add(
            AttributeOptionAlias(
                attribute_definition_id=option.attribute_definition_id,
                option_id=option.id,
                alias=alias.strip(),
                normalized_alias=normalized,
            )
        )

    async def create_alias(
        self, option_id: uuid.UUID, data: AttributeAliasCreate
    ) -> AttributeOptionAlias:
        option = await self._required(AttributeOption, option_id, "Attribute option")
        alias = await self._create_alias(option, data.alias)
        await self._event("ATTRIBUTE_OPTION", option.id, "ALIAS_CREATED")
        return await self._commit(alias)

    async def delete_alias(self, alias_id: uuid.UUID) -> None:
        alias = await self._required(AttributeOptionAlias, alias_id, "Attribute alias")
        option_id = alias.option_id
        await self.session.delete(alias)
        await self.session.flush()
        await self._event("ATTRIBUTE_OPTION", option_id, "ALIAS_DELETED")
        await self._commit()

    async def create_rule(
        self, attribute_id: uuid.UUID, data: NormalizationRuleCreate
    ) -> AttributeNormalizationRule:
        await self._required(AttributeDefinition, attribute_id, "Attribute definition")
        self._validate_rule_pattern(data.rule_type, data.pattern)
        rule = AttributeNormalizationRule(
            attribute_definition_id=attribute_id,
            rule_type=data.rule_type.value,
            pattern=data.pattern,
            replacement=data.replacement,
            priority=data.priority,
            case_sensitive=data.case_sensitive,
            description=data.description,
        )
        await self.repository.add(rule)
        return await self._commit(rule)

    async def update_rule(
        self, rule_id: uuid.UUID, data: NormalizationRuleUpdate
    ) -> AttributeNormalizationRule:
        rule = await self._required(
            AttributeNormalizationRule, rule_id, "Normalization rule"
        )
        changes = data.model_dump(exclude_unset=True)
        candidate_type = changes.get("rule_type", rule.rule_type)
        candidate_pattern = changes.get("pattern", rule.pattern)
        self._validate_rule_pattern(candidate_type, candidate_pattern)
        await self.repository.mutate(rule, changes)
        return await self._commit(rule)

    async def deactivate_rule(self, rule_id: uuid.UUID) -> None:
        await self.update_rule(rule_id, NormalizationRuleUpdate(is_active=False))

    @staticmethod
    def _alias_key(alias: str) -> str:
        return " ".join(alias.strip().split()).casefold()


__all__ = ["AttributeOptionService"]
