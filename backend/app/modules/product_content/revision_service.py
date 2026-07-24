from __future__ import annotations

import difflib
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.security import current_actor_id
from app.modules.catalog.models import Product
from app.modules.product_content.constants import (
    ContentSource,
    WORKFLOW_TRANSITIONS,
    WorkflowStatus,
)
from app.modules.product_content.models import (
    ContentType,
    Language,
    ProductContent,
)
from app.modules.product_content.schemas import (
    ContentWrite,
    WorkflowRequest,
)

from app.modules.product_content.service_support import (
    ServiceBase,
    validate_schedule,
)


class RevisionService(ServiceBase):
    async def _build_revision(
        self,
        current: ProductContent,
        data: ContentWrite,
    ) -> ProductContent:
        current.is_current = False
        entity = ProductContent(
            content_key=current.content_key,
            product_id=current.product_id,
            revision=current.revision + 1,
            content_hash=hashlib.sha256(data.content.strip().encode()).hexdigest(),
            **data.model_dump(),
        )
        await self.repository.add(entity)
        await self.event(entity, "REVISED", current.product_id)
        return entity

    async def create_content(
        self,
        product_id: uuid.UUID,
        data: ContentWrite,
    ) -> ProductContent:
        validate_schedule(data.publish_at, data.expire_at)
        await self.required(Product, product_id, "Product")
        await self.required(Language, data.language_id, "Language")
        await self.required(ContentType, data.content_type_id, "Content type")
        digest = hashlib.sha256(data.content.strip().encode()).hexdigest()
        duplicate = await self.repository.duplicate_content(digest)
        entity = ProductContent(
            product_id=product_id,
            content_hash=digest,
            duplicate_of_id=duplicate.id if duplicate else None,
            **data.model_dump(),
        )
        return await self.mutate_with_event(entity, "CREATED", product_id)

    async def revise_content(
        self,
        content_id: uuid.UUID,
        data: ContentWrite,
    ) -> ProductContent:
        validate_schedule(data.publish_at, data.expire_at)
        current = await self.required_for_update(ProductContent, content_id, "Content")
        if not current.is_current:
            raise HTTPException(
                status_code=409,
                detail="Only the current revision can be edited",
            )
        try:
            entity = await self._build_revision(current, data)
            return await self.commit(entity)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Content constraint conflict"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def workflow(
        self,
        content_id: uuid.UUID,
        data: WorkflowRequest,
    ) -> ProductContent:
        current = await self.required_for_update(ProductContent, content_id, "Content")
        try:
            requested = WorkflowStatus(data.status)
            current_status = WorkflowStatus(current.status)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail="Invalid content status transition",
            ) from exc
        if requested not in WORKFLOW_TRANSITIONS[current_status]:
            raise HTTPException(
                status_code=409,
                detail="Invalid content status transition",
            )
        actor = current_actor_id() or data.actor
        payload = ContentWrite(
            language_id=current.language_id,
            content_type_id=current.content_type_id,
            title=current.title,
            subtitle=current.subtitle,
            content=current.content,
            summary=current.summary,
            status=requested,
            approval_status=requested,
            source_type=ContentSource(current.source_type),
            source_reference=current.source_reference,
            source_metadata=current.source_metadata,
            created_by=actor,
            publish_at=current.publish_at,
            expire_at=current.expire_at,
            campaign=current.campaign,
            priority=current.priority,
        )
        try:
            revised = await self._build_revision(current, payload)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Content constraint conflict"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        if requested is WorkflowStatus.APPROVED:
            revised.approved_by = actor
            revised.approved_at = datetime.now(UTC)
        if requested is WorkflowStatus.PUBLISHED:
            revised.published_at = datetime.now(UTC)
        await self.event(revised, requested, revised.product_id)
        return await self.commit(revised)

    async def history(self, content_key: uuid.UUID) -> list[ProductContent]:
        return await self.repository.content_history(content_key)

    async def history_page(
        self,
        content_key: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[ProductContent], int]:
        return await self.repository.content_history_page(
            content_key,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )

    async def rollback(
        self,
        content_key: uuid.UUID,
        revision: int,
        actor: str | None,
    ) -> ProductContent:
        source = await self.repository.content_revision(content_key, revision)
        current = await self.repository.current_content(content_key)
        if source is None:
            raise HTTPException(status_code=404, detail="Content revision not found")
        if current is None:
            raise HTTPException(
                status_code=409,
                detail="Current content revision changed",
            )
        return await self.revise_content(
            current.id,
            ContentWrite(
                language_id=source.language_id,
                content_type_id=source.content_type_id,
                title=source.title,
                subtitle=source.subtitle,
                content=source.content,
                summary=source.summary,
                source_reference=f"rollback:{revision}",
                created_by=current_actor_id() or actor,
                publish_at=source.publish_at,
                expire_at=source.expire_at,
                campaign=source.campaign,
                priority=source.priority,
            ),
        )

    async def diff(
        self,
        content_key: uuid.UUID,
        from_revision: int,
        to_revision: int,
    ) -> dict[str, Any]:
        before = await self.repository.content_revision(content_key, from_revision)
        after = await self.repository.content_revision(content_key, to_revision)
        if before is None or after is None:
            raise HTTPException(status_code=404, detail="Content revision not found")
        return {
            "content_key": content_key,
            "from_revision": from_revision,
            "to_revision": to_revision,
            "diff": list(
                difflib.unified_diff(
                    before.content.splitlines(),
                    after.content.splitlines(),
                    lineterm="",
                )
            ),
        }
