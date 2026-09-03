from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.enums import AttributeScope
from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate,
    AttributeTypeCreate,
    AttributeTypeUpdate,
    AttributeUpdate,
    CategoryAttributeReorder,
)
from app.modules.catalog.utils import stable_code


class LegacyAttributeService:
    """Commands for legacy attributes and the Attribute Type API façade."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    async def create_attribute(
        self,
        data: AttributeCreate,
    ) -> AttributeDefinition:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv atributa ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_attribute_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod atributa ve\u0107 postoji",
            )

        if data.category_id is not None and not await self.repository.get_category(
            data.category_id
        ):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije prona\u0111ena",
            )

        attribute = AttributeDefinition(
            name=name,
            code=code,
            slug=code,
            internal_name=stable_code(data.api_name or code),
            scope=data.scope.value,
            data_type=data.data_type.value,
            unit=data.unit,
            description=data.description,
            ai_prompt=data.ai_prompt,
            example_value=data.example_value,
            validation_rules=data.validation_rules,
            api_name=stable_code(data.api_name or code),
            is_required=data.is_required,
            is_visible=data.is_visible,
            is_filterable=data.is_filterable,
            is_searchable=data.is_searchable,
            allows_multiple=data.allows_multiple,
        )

        try:
            await self.repository.create_attribute(attribute)

            if data.scope == AttributeScope.GLOBAL:
                await self.repository.link_global_attribute_to_all_categories(
                    attribute.id
                )
            else:
                assert data.category_id is not None
                await self.repository.link_attribute(
                    category_id=data.category_id,
                    attribute_id=attribute.id,
                    position=data.position,
                    group_name=data.group_name,
                )

            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut ve\u0107 postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute)
        return attribute

    async def update_attribute(
        self,
        attribute_id: uuid.UUID,
        data: AttributeUpdate,
    ) -> AttributeDefinition:
        attribute = await self.repository.get_attribute(attribute_id)

        if attribute is None:
            raise HTTPException(
                status_code=404,
                detail="Atribut nije prona\u0111en",
            )

        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            name = changes["name"].strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Naziv atributa ne sme biti prazan",
                )

            changes["name"] = name

        if "data_type" in changes and changes["data_type"] is not None:
            changes["data_type"] = changes["data_type"].value

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(attribute, field) != value
        }

        if actual_changes:
            actual_changes["version"] = attribute.version + 1

        try:
            await self.repository.update_attribute(
                attribute,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Atribut ve\u0107 postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute)
        return attribute

    async def reorder_category_attributes(
        self,
        category_id: uuid.UUID,
        data: CategoryAttributeReorder,
    ) -> None:
        if not await self.repository.get_category(category_id):
            raise HTTPException(
                status_code=404,
                detail="Kategorija nije prona\u0111ena",
            )

        try:
            for item in data.items:
                link = await self.repository.get_category_attribute(
                    category_id,
                    item.attribute_id,
                )

                if link is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Atribut {item.attribute_id} nije povezan sa kategorijom"
                        ),
                    )

                await self.repository.update_category_attribute(
                    link,
                    position=item.position,
                    group_name=item.group_name,
                )

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def list_attribute_types(
        self,
        *,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AttributeDefinition], int]:
        return await self.repository.list_attribute_types(
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def _get_attribute_type_or_404(
        self,
        attribute_type_id: uuid.UUID,
    ) -> AttributeDefinition:
        attribute_type = await self.repository.get_attribute_type(attribute_type_id)

        if attribute_type is None:
            raise HTTPException(
                status_code=404,
                detail="Tip atributa nije prona\u0111en",
            )

        return attribute_type

    async def get_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
    ) -> AttributeDefinition:
        return await self._get_attribute_type_or_404(attribute_type_id)

    async def create_attribute_type(
        self,
        data: AttributeTypeCreate,
    ) -> AttributeDefinition:
        name = data.name.strip()

        if not name:
            raise HTTPException(
                status_code=422,
                detail="Naziv tipa atributa ne sme biti prazan",
            )

        code = stable_code(data.code or name)

        if await self.repository.get_attribute_type_by_code(code):
            raise HTTPException(
                status_code=409,
                detail="Kod tipa atributa ve\u0107 postoji",
            )

        attribute_type = AttributeDefinition(
            name=name,
            code=code,
            slug=code,
            internal_name=stable_code(data.api_name or code),
            scope=data.scope.value,
            data_type=data.data_type.value,
            unit=self._normalize_optional(data.unit),
            description=self._normalize_optional(data.description),
            ai_prompt=self._normalize_optional(data.ai_prompt),
            example_value=self._normalize_optional(data.example_value),
            validation_rules=data.validation_rules,
            api_name=stable_code(data.api_name or code),
            is_required=data.is_required,
            is_visible=data.is_visible,
            is_filterable=data.is_filterable,
            is_searchable=data.is_searchable,
            allows_multiple=data.allows_multiple,
        )

        try:
            await self.repository.create_attribute_type(attribute_type)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Kod tipa atributa ve\u0107 postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)
        return attribute_type

    async def update_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
        data: AttributeTypeUpdate,
    ) -> AttributeDefinition:
        attribute_type = await self._get_attribute_type_or_404(attribute_type_id)
        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            changes["name"] = changes["name"].strip()

        if "data_type" in changes and changes["data_type"] is not None:
            changes["data_type"] = changes["data_type"].value

        for field in (
            "unit",
            "description",
            "ai_prompt",
            "example_value",
        ):
            if field in changes:
                changes[field] = self._normalize_optional(changes[field])

        if "api_name" in changes and changes["api_name"] is not None:
            changes["api_name"] = stable_code(changes["api_name"])

        actual_changes = {
            field: value
            for field, value in changes.items()
            if getattr(attribute_type, field) != value
        }

        if actual_changes:
            actual_changes["version"] = attribute_type.version + 1

        try:
            await self.repository.update_attribute_type(
                attribute_type,
                actual_changes,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Tip atributa ve\u0107 postoji",
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)
        return attribute_type

    async def deactivate_attribute_type(
        self,
        attribute_type_id: uuid.UUID,
    ) -> None:
        attribute_type = await self._get_attribute_type_or_404(attribute_type_id)

        if not attribute_type.is_active:
            return

        try:
            await self.repository.deactivate_attribute_type(attribute_type)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(attribute_type)

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


__all__ = ["LegacyAttributeService"]
