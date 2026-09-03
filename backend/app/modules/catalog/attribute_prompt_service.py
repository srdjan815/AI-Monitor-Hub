from __future__ import annotations

import uuid
from datetime import UTC, datetime
from difflib import unified_diff

from sqlalchemy import func, select, update

from app.modules.catalog.models import AttributeDefinition
from app.modules.catalog.platform_models import AttributePromptVersion
from app.modules.catalog.platform_service_support import _PlatformServiceSupport
from app.modules.catalog.schemas.attribute_platform import PromptVersionCreate


class AttributePromptService(_PlatformServiceSupport):
    """Owns versioned extraction, normalization, and validation prompts."""

    async def create_prompt(
        self,
        attribute_id: uuid.UUID,
        data: PromptVersionCreate,
    ) -> AttributePromptVersion:
        definition = await self._required(
            AttributeDefinition,
            attribute_id,
            "Attribute",
        )
        maximum = int(
            await self.session.scalar(
                select(func.max(AttributePromptVersion.version_number)).where(
                    AttributePromptVersion.attribute_definition_id == attribute_id
                )
            )
            or 0
        )
        if data.activate:
            await self.session.execute(
                update(AttributePromptVersion)
                .where(AttributePromptVersion.attribute_definition_id == attribute_id)
                .values(is_active=False)
            )
        prompt = AttributePromptVersion(
            attribute_definition_id=attribute_id,
            version_number=maximum + 1,
            description=data.description,
            extraction_prompt=data.extraction_prompt,
            normalization_prompt=data.normalization_prompt,
            validation_prompt=data.validation_prompt,
            examples=data.examples,
            negative_examples=data.negative_examples,
            normalization_examples=data.normalization_examples,
            validation_examples=data.validation_examples,
            is_active=data.activate,
            activated_at=datetime.now(UTC) if data.activate else None,
        )
        self.session.add(prompt)
        if data.activate:
            definition.extraction_prompt = data.extraction_prompt
            definition.normalization_prompt = data.normalization_prompt
            definition.validation_prompt = data.validation_prompt
            definition.examples = data.examples
            definition.version += 1
        await self.session.flush()
        return await self._commit(prompt)

    async def list_prompt_versions(
        self,
        attribute_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AttributePromptVersion]:
        await self._required(AttributeDefinition, attribute_id, "Attribute")
        return await self.repository.list_prompt_versions(
            attribute_id,
            offset=offset,
            limit=limit,
        )

    async def activate_prompt(
        self,
        prompt_id: uuid.UUID,
    ) -> AttributePromptVersion:
        prompt = await self._required(
            AttributePromptVersion,
            prompt_id,
            "Prompt version",
        )
        await self.session.execute(
            update(AttributePromptVersion)
            .where(
                AttributePromptVersion.attribute_definition_id
                == prompt.attribute_definition_id
            )
            .values(is_active=False)
        )
        prompt.is_active = True
        prompt.activated_at = datetime.now(UTC)
        definition = await self._required(
            AttributeDefinition,
            prompt.attribute_definition_id,
            "Attribute",
        )
        definition.extraction_prompt = prompt.extraction_prompt
        definition.normalization_prompt = prompt.normalization_prompt
        definition.validation_prompt = prompt.validation_prompt
        definition.examples = prompt.examples
        definition.version += 1
        return await self._commit(prompt)

    async def prompt_diff(
        self,
        left_id: uuid.UUID,
        right_id: uuid.UUID,
    ) -> dict[str, str]:
        left = await self._required(
            AttributePromptVersion,
            left_id,
            "Prompt",
        )
        right = await self._required(
            AttributePromptVersion,
            right_id,
            "Prompt",
        )
        fields = (
            "extraction_prompt",
            "normalization_prompt",
            "validation_prompt",
        )
        return {
            field: "\n".join(
                unified_diff(
                    (getattr(left, field) or "").splitlines(),
                    (getattr(right, field) or "").splitlines(),
                    fromfile=f"v{left.version_number}",
                    tofile=f"v{right.version_number}",
                    lineterm="",
                )
            )
            for field in fields
        }
