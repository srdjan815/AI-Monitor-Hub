from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.platform_models import AttributeDependency
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import DependencyCreate


class AttributeDependencyService(_PlatformServiceSupport):
    """Owns cross-attribute dependency rules and product validation."""

    async def create_dependency(
        self,
        data: DependencyCreate,
    ) -> AttributeDependency:
        await self._required(
            AttributeDefinition,
            data.source_attribute_id,
            "Source attribute",
        )
        await self._required(
            AttributeDefinition,
            data.target_attribute_id,
            "Target attribute",
        )
        dependency = AttributeDependency(**data.model_dump())
        self.session.add(dependency)
        await self.session.flush()
        return await self._commit(dependency)

    async def list_dependencies(
        self,
        *,
        active_only: bool,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributeDependency]:
        return await self.repository.list_dependencies(
            active_only=active_only,
            offset=offset,
            limit=limit,
        )

    async def deactivate_dependency(
        self,
        dependency_id: uuid.UUID,
    ) -> None:
        dependency = await self._required(
            AttributeDependency,
            dependency_id,
            "Dependency",
        )
        dependency.is_active = False
        await self._commit()

    async def validate_dependencies(
        self,
        product_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        values = {
            item.attribute_definition_id: item.canonical_value
            for item in await self.repository.values(product_id)
        }
        rules = (
            (
                await self.session.execute(
                    select(AttributeDependency).where(
                        AttributeDependency.is_active.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )
        errors: list[dict[str, Any]] = []
        for rule in rules:
            source = values.get(rule.source_attribute_id)
            target = values.get(rule.target_attribute_id)
            config = rule.rule_config
            if (
                rule.dependency_type == "REQUIRED"
                and source in config.get("when_source_in", [])
                and target in (None, "", [])
            ):
                errors.append(
                    {
                        "dependency_id": rule.id,
                        "message": "Required value missing",
                    }
                )
            if (
                rule.dependency_type == "ALLOWED_VALUES"
                and source in config.get("when_source_in", [source])
                and target is not None
                and target not in config.get("allowed_values", [])
            ):
                errors.append(
                    {
                        "dependency_id": rule.id,
                        "message": "Value is not allowed",
                    }
                )
        return errors
