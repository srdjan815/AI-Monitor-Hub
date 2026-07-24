from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.modules.catalog.models import Product
from app.modules.product_content.models import (
    DocumentReference,
    LandingPage,
    Language,
    ProductSEO,
    VideoReference,
)
from app.modules.product_content.schemas import (
    LandingWrite,
    LinkCheckWrite,
    ReferenceWrite,
    SEOWrite,
)

from app.modules.product_content.service_support import (
    ServiceBase,
    usage_payload,
    validate_schedule,
)


class ReferenceService(ServiceBase):
    MODELS = {
        "document": (DocumentReference, "url"),
        "video": (VideoReference, "url"),
        "seo": (ProductSEO, "slug"),
        "landing": (LandingPage, "slug"),
    }

    async def create_document(
        self,
        product_id: uuid.UUID,
        data: ReferenceWrite,
    ) -> DocumentReference:
        await self.required(Product, product_id, "Product")
        values = data.model_dump(
            exclude={"reference_type", "thumbnail_reference", "sort_order"}
        )
        entity = DocumentReference(
            product_id=product_id,
            document_type=data.reference_type,
            **values,
        )
        return await self.mutate_with_event(entity, "CREATED", product_id)

    async def create_video(
        self,
        product_id: uuid.UUID,
        data: ReferenceWrite,
    ) -> VideoReference:
        await self.required(Product, product_id, "Product")
        entity = VideoReference(
            product_id=product_id,
            video_type=data.reference_type,
            title=data.title,
            url=data.url,
            language_id=data.language_id,
            thumbnail_reference=data.thumbnail_reference,
            sort_order=data.sort_order,
        )
        return await self.mutate_with_event(entity, "CREATED", product_id)

    async def list_references(
        self,
        kind: str,
        product_id: uuid.UUID | None,
        active_only: bool,
        *,
        offset: int,
        limit: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[Any]:
        return await self.repository.references(
            self.MODELS[kind][0],
            product_id,
            active_only,
            offset=offset,
            limit=limit,
            snapshot_at=snapshot_at,
            after=after,
        )

    async def get_reference(self, kind: str, entity_id: uuid.UUID) -> Any:
        return await self.required(self.MODELS[kind][0], entity_id, kind.title())

    async def update_reference(
        self,
        kind: str,
        entity_id: uuid.UUID,
        data: ReferenceWrite,
    ) -> Any:
        entity = await self.get_reference(kind, entity_id)
        entity.title = data.title
        entity.url = data.url
        entity.language_id = data.language_id
        if kind == "document":
            entity.document_type = data.reference_type
            entity.version = data.version
        else:
            entity.video_type = data.reference_type
            entity.thumbnail_reference = data.thumbnail_reference
            entity.sort_order = data.sort_order
        return await self.commit(entity)

    async def deactivate_reference(
        self,
        kind: str,
        entity_id: uuid.UUID,
    ) -> Any:
        entity = await self.get_reference(kind, entity_id)
        entity.is_active = False
        return await self.commit(entity)

    async def update_link(
        self,
        kind: str,
        entity_id: uuid.UUID,
        data: LinkCheckWrite,
    ) -> Any:
        entity = await self.get_reference(kind, entity_id)
        entity.link_status = data.status
        entity.link_error = data.error
        entity.last_checked_at = data.checked_at or datetime.now(UTC)
        entity.next_check_at = data.next_check_at
        return await self.commit(entity)

    async def create_seo(
        self,
        product_id: uuid.UUID,
        data: SEOWrite,
    ) -> ProductSEO:
        await self.required(Product, product_id, "Product")
        await self.required(Language, data.language_id, "Language")
        entity = ProductSEO(product_id=product_id, **data.model_dump())
        return await self.mutate_with_event(entity, "CREATED", product_id)

    async def create_landing(
        self,
        product_id: uuid.UUID,
        data: LandingWrite,
    ) -> LandingPage:
        validate_schedule(data.publish_at, data.expire_at)
        await self.required(Product, product_id, "Product")
        await self.required(Language, data.language_id, "Language")
        entity = LandingPage(
            product_id=product_id,
            **data.model_dump(),
        )
        return await self.mutate_with_event(entity, "CREATED", product_id)

    async def list_revisions(
        self,
        kind: str,
        product_id: uuid.UUID | None,
        current_only: bool,
        *,
        offset: int,
        limit: int,
        snapshot_at: datetime | None = None,
        after: tuple[datetime, uuid.UUID] | None = None,
    ) -> list[Any]:
        return await self.repository.revision_entities(
            self.MODELS[kind][0],
            product_id,
            current_only,
            offset=offset,
            limit=limit,
            snapshot_at=snapshot_at,
            after=after,
        )

    async def revise_seo(
        self,
        seo_id: uuid.UUID,
        data: SEOWrite,
    ) -> ProductSEO:
        current = await self.required_for_update(ProductSEO, seo_id, "SEO")
        if not current.is_current:
            raise HTTPException(
                status_code=409, detail="Only current SEO may be revised"
            )
        current.is_current = False
        return await self.mutate(
            ProductSEO(
                seo_key=current.seo_key,
                product_id=current.product_id,
                revision=current.revision + 1,
                **data.model_dump(),
            )
        )

    async def revise_landing(
        self,
        page_id: uuid.UUID,
        data: LandingWrite,
    ) -> LandingPage:
        validate_schedule(data.publish_at, data.expire_at)
        current = await self.required_for_update(LandingPage, page_id, "Landing page")
        if not current.is_current:
            raise HTTPException(
                status_code=409,
                detail="Only current landing page may be revised",
            )
        current.is_current = False
        return await self.mutate(
            LandingPage(
                landing_key=current.landing_key,
                product_id=current.product_id,
                revision=current.revision + 1,
                **data.model_dump(),
            )
        )

    async def deactivate_revision(self, kind: str, entity_id: uuid.UUID) -> Any:
        entity = await self.required(self.MODELS[kind][0], entity_id, kind.title())
        setattr(entity, "is_current", False)
        return await self.commit(entity)

    async def revision_history(
        self,
        kind: str,
        key: uuid.UUID,
    ) -> list[Any]:
        model = self.MODELS[kind][0]
        key_column = ProductSEO.seo_key if kind == "seo" else LandingPage.landing_key
        return await self.repository.revision_history(model, key_column, key)

    async def revision_history_page(
        self,
        kind: str,
        key: uuid.UUID,
        *,
        limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[Any], int]:
        model = self.MODELS[kind][0]
        key_column = ProductSEO.seo_key if kind == "seo" else LandingPage.landing_key
        return await self.repository.revision_history_page(
            model,
            key_column,
            key,
            limit=limit,
            after_revision=after_revision,
            snapshot_revision=snapshot_revision,
        )

    async def rollback_revision(
        self,
        kind: str,
        key: uuid.UUID,
        revision: int,
    ) -> Any:
        model = self.MODELS[kind][0]
        key_name = "seo_key" if kind == "seo" else "landing_key"
        key_column = getattr(model, key_name)
        history = await self.repository.revision_history(model, key_column, key)
        source = next((row for row in history if row.revision == revision), None)
        current = next((row for row in history if row.is_current), None)
        latest = history[0] if history else None
        if source is None or latest is None:
            raise HTTPException(
                status_code=404,
                detail=f"{kind.title()} revision not found",
            )
        if current is not None:
            current.is_current = False
        excluded = {
            "id",
            "created_at",
            "updated_at",
            "revision",
            "is_current",
            key_name,
            "product_id",
        }
        values = {
            column.name: getattr(source, column.name)
            for column in source.__table__.columns
            if column.name not in excluded
        }
        entity = model(
            **{
                key_name: key,
                "product_id": latest.product_id,
                "revision": latest.revision + 1,
                **values,
            }
        )
        return await self.mutate(entity)

    async def usage(
        self,
        kind: str,
        entity_id: uuid.UUID,
    ) -> dict[str, Any]:
        model, field_name = self.MODELS[kind]
        entity = await self.required(model, entity_id, kind.title())
        value = getattr(entity, field_name)
        rows = await self.repository.related_by_value(
            model, getattr(model, field_name), value
        )
        return usage_payload(entity_id, rows, kind, value)
