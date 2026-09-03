from __future__ import annotations

import builtins
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.models import Product
from app.modules.catalog.utils import stable_code
from app.modules.product_content.models import (
    ContentLibraryItem,
    ContentTemplate,
    ContentTemplateCondition,
    ContentTemplateItem,
    ProductContentTemplate,
)
from app.modules.product_content.schemas import (
    TemplateConditionWrite,
    TemplateItemWrite,
    TemplateUpdate,
    TemplateWrite,
)

from app.modules.product_content.service_support import (
    ServiceBase,
    serialize,
)


class TemplateService(ServiceBase):
    async def create(self, data: TemplateWrite) -> ContentTemplate:
        return await self.mutate(
            ContentTemplate(
                name=data.name,
                slug=stable_code(data.slug or data.name),
                description=data.description,
            )
        )

    async def list(
        self,
        active_only: bool,
        *,
        offset: int,
        limit: int,
    ) -> list[ContentTemplate]:
        return await self.repository.templates(
            active_only,
            offset=offset,
            limit=limit,
        )

    async def get(self, template_id: uuid.UUID) -> ContentTemplate:
        return await self.required(ContentTemplate, template_id, "Template")

    async def detail(self, template_id: uuid.UUID) -> dict[str, Any]:
        result = serialize(await self.get(template_id))
        result["items"] = [
            serialize(item)
            for item in await self.repository.template_items(template_id)
        ]
        return result

    async def update(
        self,
        template_id: uuid.UUID,
        data: TemplateUpdate,
    ) -> ContentTemplate:
        entity = await self.get(template_id)
        changed = False
        for field, value in data.model_dump(exclude_unset=True).items():
            if getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
        if changed:
            entity.version += 1
        return await self.commit(entity)

    async def deactivate(self, template_id: uuid.UUID) -> ContentTemplate:
        entity = await self.get(template_id)
        entity.is_active = False
        return await self.commit(entity)

    async def add_item(
        self,
        template_id: uuid.UUID,
        data: TemplateItemWrite,
    ) -> ContentTemplateItem:
        await self.get(template_id)
        await self.required(ContentLibraryItem, data.library_item_id, "Library item")
        return await self.mutate(
            ContentTemplateItem(template_id=template_id, **data.model_dump())
        )

    async def update_item(
        self,
        item_id: uuid.UUID,
        data: TemplateItemWrite,
    ) -> ContentTemplateItem:
        entity = await self.required_for_update(
            ContentTemplateItem, item_id, "Template item"
        )
        for field, value in data.model_dump().items():
            setattr(entity, field, value)
        return await self.commit(entity)

    async def delete_item(self, item_id: uuid.UUID) -> None:
        entity = await self.required(ContentTemplateItem, item_id, "Template item")
        await self.repository.delete(entity)
        await self.commit()

    async def add_condition(
        self,
        item_id: uuid.UUID,
        data: TemplateConditionWrite,
    ) -> ContentTemplateCondition:
        await self.required(ContentTemplateItem, item_id, "Template item")
        return await self.mutate(
            ContentTemplateCondition(
                template_item_id=item_id,
                **data.model_dump(),
            )
        )

    async def conditions(
        self,
        item_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
    ) -> builtins.list[ContentTemplateCondition]:
        await self.required(ContentTemplateItem, item_id, "Template item")
        return await self.repository.template_conditions(
            [item_id],
            offset=offset,
            limit=limit,
        )

    async def clone(
        self,
        template_id: uuid.UUID,
        name: str,
    ) -> ContentTemplate:
        source = await self.get(template_id)
        clone = ContentTemplate(
            name=name,
            slug=stable_code(name),
            description=source.description,
        )
        try:
            await self.repository.add(clone)
            source_items = await self.repository.template_items(template_id)
            source_conditions = await self.repository.template_conditions(
                [item.id for item in source_items]
            )
            conditions_by_item: dict[uuid.UUID, list[ContentTemplateCondition]] = {}
            for condition in source_conditions:
                conditions_by_item.setdefault(condition.template_item_id, []).append(
                    condition
                )
            for item in source_items:
                cloned_item = await self.repository.add(
                    ContentTemplateItem(
                        template_id=clone.id,
                        library_item_id=item.library_item_id,
                        sort_order=item.sort_order,
                        condition_operator=item.condition_operator,
                        condition_source=item.condition_source,
                        condition_comparator=item.condition_comparator,
                        condition_value=item.condition_value,
                    )
                )
                for condition in conditions_by_item.get(item.id, []):
                    await self.repository.add(
                        ContentTemplateCondition(
                            template_item_id=cloned_item.id,
                            sort_order=condition.sort_order,
                            boolean_operator=condition.boolean_operator,
                            source=condition.source,
                            comparator=condition.comparator,
                            expected_value=condition.expected_value,
                        )
                    )
            return await self.commit(clone)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Content constraint conflict"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def assign(
        self,
        product_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> ProductContentTemplate:
        await self.required(Product, product_id, "Product")
        template = await self.get(template_id)
        if not template.is_active:
            raise HTTPException(
                status_code=409,
                detail="Inactive template cannot be assigned",
            )
        return await self.mutate(
            ProductContentTemplate(
                product_id=product_id,
                template_id=template_id,
            )
        )

    async def usage(self, template_id: uuid.UUID) -> dict[str, Any]:
        await self.get(template_id)
        rows = await self.repository.template_usage(template_id)
        return {
            "template_id": template_id,
            "usage_count": len(rows),
            "products": [row.product_id for row in rows],
            "last_usage": max((row.updated_at for row in rows), default=None),
        }
