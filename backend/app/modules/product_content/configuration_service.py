from __future__ import annotations

import uuid


from app.modules.catalog.utils import stable_code
from app.modules.product_content.constants import (
    DEFAULT_CONTENT_TYPES,
)
from app.modules.product_content.models import (
    ContentType,
    Language,
)
from app.modules.product_content.schemas import (
    ContentTypeCreate,
    ContentTypeUpdate,
    LanguageCreate,
    LanguageUpdate,
)

from app.modules.product_content.service_support import (
    ServiceBase,
)


class ConfigurationService(ServiceBase):
    async def create_language(self, data: LanguageCreate) -> Language:
        if data.is_default:
            for language in await self.repository.default_languages():
                language.is_default = False
        return await self.mutate(Language(**data.model_dump()))

    async def list_languages(
        self,
        active_only: bool,
        *,
        offset: int,
        limit: int,
    ) -> list[Language]:
        return await self.repository.languages(
            active_only,
            offset=offset,
            limit=limit,
        )

    async def get_language(self, language_id: uuid.UUID) -> Language:
        return await self.required(Language, language_id, "Language")

    async def update_language(
        self,
        language_id: uuid.UUID,
        data: LanguageUpdate,
    ) -> Language:
        entity = await self.get_language(language_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("is_default"):
            for language in await self.repository.default_languages(language_id):
                language.is_default = False
        for field, value in values.items():
            setattr(entity, field, value)
        return await self.commit(entity)

    async def set_language_active(
        self,
        language_id: uuid.UUID,
        active: bool,
    ) -> Language:
        entity = await self.get_language(language_id)
        entity.is_active = active
        if not active:
            entity.is_default = False
        return await self.commit(entity)

    async def create_type(self, data: ContentTypeCreate) -> ContentType:
        values = data.model_dump()
        values["slug"] = stable_code(data.slug or data.name)
        return await self.mutate(ContentType(**values))

    async def list_types(
        self,
        active_only: bool,
        *,
        offset: int,
        limit: int,
    ) -> list[ContentType]:
        return await self.repository.content_types(
            active_only,
            offset=offset,
            limit=limit,
        )

    async def get_type(self, type_id: uuid.UUID) -> ContentType:
        return await self.required(ContentType, type_id, "Content type")

    async def update_type(
        self,
        type_id: uuid.UUID,
        data: ContentTypeUpdate,
    ) -> ContentType:
        entity = await self.get_type(type_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        return await self.commit(entity)

    async def set_type_active(
        self,
        type_id: uuid.UUID,
        active: bool,
    ) -> ContentType:
        entity = await self.get_type(type_id)
        entity.is_active = active
        return await self.commit(entity)

    async def seed(self) -> dict[str, int]:
        languages = 0
        types = 0
        if await self.repository.language_by_code("sr") is None:
            await self.create_language(
                LanguageCreate(
                    code="sr",
                    name="Serbian",
                    native_name="Srpski",
                    is_default=True,
                )
            )
            languages += 1
        for order, (name, slug) in enumerate(DEFAULT_CONTENT_TYPES):
            if await self.repository.content_type_by_slug(slug) is None:
                await self.create_type(
                    ContentTypeCreate(
                        name=name,
                        slug=slug,
                        sort_order=order * 10,
                    )
                )
                types += 1
        return {"languages_created": languages, "types_created": types}
