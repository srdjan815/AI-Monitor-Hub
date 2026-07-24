from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from app.modules.product_content.completion import ContentCompletionService
from app.modules.product_content.constants import ScoreType
from app.modules.product_content.models import (
    ContentScoringPolicy,
    ContentScoreHistory,
    ProductSEO,
)
from app.modules.product_content.repositories import ContentRepository
from app.modules.product_content.schemas import PreviewRequest, ScoringPolicyWrite
from app.modules.product_content.services import ServiceBase, serialize


class ContentQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = ContentRepository(session)

    async def search_content(self, **filters: Any) -> list[Any]:
        return await self.repository.content_search(**filters)

    async def export(self, product_id: uuid.UUID) -> dict[str, Any]:
        rows = await self.repository.export_product(product_id)
        return {
            "product_id": product_id,
            "content_contract": {
                "representation": "stored_source",
                "sanitized": False,
                "publishable": False,
            },
            **{
                name: [serialize(entity) for entity in entities]
                for name, entities in rows.items()
            },
            "content_score": await ScoringService(
                self.repository.session
            ).content_score(product_id),
        }

    async def changes(self, cursor: int, limit: int) -> list[dict[str, Any]]:
        rows = await self.repository.changes(cursor, limit)
        return [
            {
                "cursor": row.cursor,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "product_id": row.product_id,
                "action": row.action,
                "occurred_at": row.occurred_at,
            }
            for row in rows
        ]

    async def global_search(self, **filters: Any) -> dict[str, Any]:
        result = await self.repository.global_search(**filters)
        return {
            name: [serialize(entity) for entity in entities]
            for name, entities in result.items()
        }


class ScoringService(ServiceBase):
    CHECK_WEIGHTS = {
        "has_short_description": "short_description_weight",
        "has_long_description": "long_description_weight",
        "has_seo": "seo_weight",
        "has_landing_page": "landing_weight",
        "has_document": "document_weight",
        "has_video": "video_weight",
        "has_translation": "translation_weight",
    }

    async def content_score(self, product_id: uuid.UUID) -> dict[str, Any]:
        await self.required(Product, product_id, "Product")
        counts = await self.repository.score_counts(product_id)
        checks = {
            "has_short_description": counts["short"] > 0,
            "has_long_description": counts["long"] > 0,
            "has_seo": counts["seo"] > 0,
            "has_landing_page": counts["landing"] > 0,
            "has_document": counts["document"] > 0,
            "has_video": counts["video"] > 0,
            "has_translation": counts["languages"] > 1,
        }
        return {
            "score": round(sum(checks.values()) / len(checks) * 100),
            "checks": checks,
        }

    async def create_policy(
        self,
        data: ScoringPolicyWrite,
    ) -> ContentScoringPolicy:
        return await self.mutate(ContentScoringPolicy(**data.model_dump()))

    async def policies(
        self,
        active_only: bool,
        *,
        offset: int,
        limit: int,
    ) -> list[ContentScoringPolicy]:
        return await self.repository.scoring_policies(
            active_only,
            offset=offset,
            limit=limit,
        )

    async def weighted_score(
        self,
        product_id: uuid.UUID,
        policy_id: uuid.UUID,
    ) -> dict[str, Any]:
        policy = await self.required(ContentScoringPolicy, policy_id, "Scoring policy")
        checks = (await self.content_score(product_id))["checks"]
        weights = {
            check: getattr(policy, field) for check, field in self.CHECK_WEIGHTS.items()
        }
        total = sum(weights.values())
        earned = sum(weight for check, weight in weights.items() if checks[check])
        mandatory_missing = [
            section
            for section in policy.mandatory_sections
            if not checks.get(f"has_{section}", False)
        ]
        score = round(earned / total * 100) if total else 0
        await self.mutate(
            ContentScoreHistory(
                product_id=product_id,
                policy_id=policy.id,
                score_type=ScoreType.CONTENT,
                score=score,
            )
        )
        return {
            "score": score,
            "checks": checks,
            "weights": weights,
            "mandatory_missing": mandatory_missing,
        }

    async def seo_score(
        self,
        product_id: uuid.UUID,
        seo_id: uuid.UUID,
    ) -> dict[str, Any]:
        entity = await self.required(ProductSEO, seo_id, "SEO")
        if entity.product_id != product_id:
            raise HTTPException(status_code=404, detail="SEO not found for product")
        checks = {
            "title": 20 <= len(entity.seo_title) <= 60,
            "description": 70 <= len(entity.seo_description) <= 160,
            "keywords": bool(entity.seo_keywords),
            "slug": bool(entity.slug),
            "canonical": bool(entity.canonical_url),
            "schema": bool(entity.schema_org),
            "open_graph": bool(entity.open_graph),
            "twitter": bool(entity.twitter_card),
            "unique": await self.repository.seo_duplicate_count(entity) == 0,
        }
        score = round(sum(checks.values()) / len(checks) * 100)
        await self.mutate(
            ContentScoreHistory(
                product_id=product_id,
                score_type=ScoreType.SEO,
                score=score,
            )
        )
        return {"score": score, "checks": checks}

    async def history(
        self,
        product_id: uuid.UUID,
        score_type: str | None,
        *,
        offset: int,
        limit: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[ContentScoreHistory]:
        return await self.repository.score_history(
            product_id,
            score_type,
            offset=offset,
            limit=limit,
            snapshot_at=snapshot_at,
            after=after,
        )


class PreviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.delegate = ContentCompletionService(session)

    async def variables(self, product_id: uuid.UUID) -> dict[str, Any]:
        return {
            "product_id": product_id,
            "variables": await self.delegate.variables(product_id),
        }

    async def render(
        self,
        product_id: uuid.UUID,
        template_id: uuid.UUID,
        data: PreviewRequest,
    ) -> dict[str, Any]:
        return await self.delegate.render(product_id, template_id, data)
