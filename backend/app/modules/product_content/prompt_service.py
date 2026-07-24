from __future__ import annotations

import uuid


from app.modules.product_content.models import (
    ContentType,
    ContentTypePromptVersion,
)
from app.modules.product_content.schemas import (
    PromptWrite,
)

from app.modules.product_content.service_support import (
    ServiceBase,
)


class PromptService(ServiceBase):
    async def create(
        self,
        type_id: uuid.UUID,
        data: PromptWrite,
    ) -> ContentTypePromptVersion:
        await self.required_for_update(ContentType, type_id, "Content type")
        for prompt in await self.repository.active_prompts(type_id):
            prompt.is_active = False
        await self.repository.flush()
        return await self.mutate(
            ContentTypePromptVersion(
                content_type_id=type_id,
                version=await self.repository.next_prompt_version(type_id),
                **data.model_dump(),
            )
        )

    async def history(
        self,
        type_id: uuid.UUID,
    ) -> list[ContentTypePromptVersion]:
        await self.required(ContentType, type_id, "Content type")
        return await self.repository.prompt_history(type_id)

    async def history_page(
        self,
        type_id: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[ContentTypePromptVersion], int]:
        await self.required(ContentType, type_id, "Content type")
        return await self.repository.prompt_history_page(
            type_id,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )

    async def activate(
        self,
        prompt_id: uuid.UUID,
    ) -> ContentTypePromptVersion:
        entity = await self.required(ContentTypePromptVersion, prompt_id, "Prompt")
        await self.required_for_update(
            ContentType,
            entity.content_type_id,
            "Content type",
        )
        for prompt in await self.repository.prompts_for_type(entity.content_type_id):
            prompt.is_active = False
        await self.repository.flush()
        entity.is_active = True
        return await self.commit(entity)
