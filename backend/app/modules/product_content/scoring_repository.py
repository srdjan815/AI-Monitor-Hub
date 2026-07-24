from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.modules.catalog.attribute_models import ProductAttributeValue
from app.modules.catalog.models import AttributeDefinition
from app.modules.product_content.models import (
    ContentLibraryItem,
    ContentScoringPolicy,
    ContentScoreHistory,
    ContentTemplate,
    ContentType,
    ContentTypePromptVersion,
    DocumentReference,
    LandingPage,
    ProductContent,
    ProductSEO,
    VideoReference,
)
from app.modules.product_content.repository_support import ContentRepositorySupport


class ScoringRepository(ContentRepositorySupport):
    async def product_attribute_variables(
        self,
        product_id: uuid.UUID,
    ) -> list[tuple[ProductAttributeValue, str]]:
        result = await self.session.execute(
            select(ProductAttributeValue, AttributeDefinition.api_name)
            .join(
                AttributeDefinition,
                AttributeDefinition.id == ProductAttributeValue.attribute_definition_id,
            )
            .where(
                ProductAttributeValue.product_id == product_id,
                ProductAttributeValue.is_active.is_(True),
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def score_counts(self, product_id: uuid.UUID) -> dict[str, int]:
        short_slug = "short_description"
        long_slug = "long_description"
        content_counts = (
            select(
                func.count(ProductContent.id)
                .filter(ContentType.slug == short_slug)
                .label("short"),
                func.count(ProductContent.id)
                .filter(ContentType.slug == long_slug)
                .label("long"),
                func.count(func.distinct(ProductContent.language_id)).label(
                    "languages"
                ),
            )
            .select_from(ProductContent)
            .join(ContentType, ContentType.id == ProductContent.content_type_id)
            .where(
                ProductContent.product_id == product_id,
                ProductContent.is_current.is_(True),
            )
            .subquery()
        )
        row = (
            await self.session.execute(
                select(
                    content_counts.c.short,
                    content_counts.c.long,
                    content_counts.c.languages,
                    select(func.count(ProductSEO.id))
                    .where(
                        ProductSEO.product_id == product_id,
                        ProductSEO.is_current.is_(True),
                    )
                    .scalar_subquery()
                    .label("seo"),
                    select(func.count(LandingPage.id))
                    .where(
                        LandingPage.product_id == product_id,
                        LandingPage.is_current.is_(True),
                    )
                    .scalar_subquery()
                    .label("landing"),
                    select(func.count(DocumentReference.id))
                    .where(
                        DocumentReference.product_id == product_id,
                        DocumentReference.is_active.is_(True),
                    )
                    .scalar_subquery()
                    .label("document"),
                    select(func.count(VideoReference.id))
                    .where(
                        VideoReference.product_id == product_id,
                        VideoReference.is_active.is_(True),
                    )
                    .scalar_subquery()
                    .label("video"),
                ).select_from(content_counts)
            )
        ).one()
        return {
            name: int(getattr(row, name) or 0)
            for name in (
                "short",
                "long",
                "languages",
                "seo",
                "landing",
                "document",
                "video",
            )
        }

    async def seo_duplicate_count(self, entity: ProductSEO) -> int:
        count = await self.session.scalar(
            select(func.count(ProductSEO.id)).where(
                ProductSEO.id != entity.id,
                ProductSEO.is_current.is_(True),
                or_(
                    ProductSEO.seo_title == entity.seo_title,
                    ProductSEO.seo_description == entity.seo_description,
                ),
            )
        )
        return int(count or 0)

    async def score_history(
        self,
        product_id: uuid.UUID,
        score_type: str | None,
        *,
        offset: int = 0,
        limit: int = 100,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ContentScoreHistory]:
        query = select(ContentScoreHistory).where(
            ContentScoreHistory.product_id == product_id
        )
        if score_type:
            query = query.where(ContentScoreHistory.score_type == score_type)
        if snapshot_at is not None:
            query = query.where(ContentScoreHistory.calculated_at <= snapshot_at)
        if after is not None:
            after_at, after_id = after
            query = query.where(
                or_(
                    ContentScoreHistory.calculated_at < after_at,
                    and_(
                        ContentScoreHistory.calculated_at == after_at,
                        ContentScoreHistory.id < after_id,
                    ),
                )
            )
        return await self.all(
            query.order_by(
                ContentScoreHistory.calculated_at.desc(),
                ContentScoreHistory.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

    async def scoring_policies(
        self,
        active_only: bool,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ContentScoringPolicy]:
        query = select(ContentScoringPolicy)
        if active_only:
            query = query.where(ContentScoringPolicy.is_active.is_(True))
        return await self.all(
            query.order_by(ContentScoringPolicy.name, ContentScoringPolicy.id)
            .offset(offset)
            .limit(limit)
        )

    async def active_prompts(
        self,
        type_id: uuid.UUID,
    ) -> list[ContentTypePromptVersion]:
        return await self.all(
            select(ContentTypePromptVersion).where(
                ContentTypePromptVersion.content_type_id == type_id,
                ContentTypePromptVersion.is_active.is_(True),
            )
        )

    async def next_prompt_version(self, type_id: uuid.UUID) -> int:
        maximum = await self.one(
            select(func.max(ContentTypePromptVersion.version)).where(
                ContentTypePromptVersion.content_type_id == type_id
            )
        )
        return int(maximum or 0) + 1

    async def prompt_history(
        self,
        type_id: uuid.UUID,
    ) -> list[ContentTypePromptVersion]:
        return await self.all(
            select(ContentTypePromptVersion)
            .where(ContentTypePromptVersion.content_type_id == type_id)
            .order_by(ContentTypePromptVersion.version.desc())
        )

    async def prompt_history_page(
        self,
        type_id: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[ContentTypePromptVersion], int]:
        rows, snapshot = await self._revision_page(
            ContentTypePromptVersion,
            ContentTypePromptVersion.content_type_id == type_id,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
            revision_column=ContentTypePromptVersion.version,
        )
        return rows, snapshot

    async def prompts_for_type(
        self,
        type_id: uuid.UUID,
    ) -> list[ContentTypePromptVersion]:
        return await self.all(
            select(ContentTypePromptVersion).where(
                ContentTypePromptVersion.content_type_id == type_id
            )
        )

    async def global_search(
        self,
        *,
        text: str,
        language_id: uuid.UUID | None,
        status: str | None,
        approval: str | None,
        offset: int,
        limit: int,
    ) -> dict[str, list[Any]]:
        pattern = f"%{text}%"
        content = select(ProductContent).where(
            ProductContent.is_current.is_(True),
            or_(
                ProductContent.title.ilike(pattern),
                ProductContent.content.ilike(pattern),
            ),
        )
        if language_id:
            content = content.where(ProductContent.language_id == language_id)
        if status:
            content = content.where(ProductContent.status == status)
        if approval:
            content = content.where(ProductContent.approval_status == approval)
        return {
            "content": await self.all(
                content.order_by(
                    ProductContent.updated_at.desc(),
                    ProductContent.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            ),
            "library": await self.all(
                select(ContentLibraryItem)
                .where(
                    or_(
                        ContentLibraryItem.name.ilike(pattern),
                        ContentLibraryItem.description.ilike(pattern),
                    )
                )
                .order_by(
                    ContentLibraryItem.updated_at.desc(),
                    ContentLibraryItem.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            ),
            "templates": await self.all(
                select(ContentTemplate)
                .where(ContentTemplate.name.ilike(pattern))
                .order_by(ContentTemplate.name, ContentTemplate.id)
                .offset(offset)
                .limit(limit)
            ),
        }


__all__ = ["ScoringRepository"]
