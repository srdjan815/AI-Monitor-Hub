from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import current_actor_id
from app.modules.suppliers.article_review_models import (
    SupplierArticleReview,
    SupplierArticleReviewEvent,
)
from app.modules.suppliers.article_review_repository import (
    ReviewRow,
    SupplierArticleReviewRepository,
)
from app.modules.suppliers.article_review_schemas import (
    ArticleReviewEventList,
    ArticleReviewEventRead,
    ArticleReviewList,
    ArticleReviewRead,
)
from app.modules.suppliers.delta_models import (
    SupplierDeltaFieldChange,
    SupplierDeltaItem,
    SupplierDeltaRun,
)
from app.modules.suppliers.errors import supplier_error
from app.modules.suppliers.snapshot_models import SupplierSnapshotItem


ISSUE_CODES = {
    "CURRENT_RECORD_INVALID": "RECORD_INVALID",
    "REMOVAL_REQUIRES_REVIEW": "ARTICLE_REMOVED",
    "EAN_CHANGE_REQUIRES_REVIEW": "EAN_CHANGED",
    "SHARED_EAN_LOW_NAME_SIMILARITY": "EAN_SHARED_BY_MULTIPLE_ARTICLES",
    "CRITICAL_PRICE_CHANGE": "CRITICAL_PRICE_CHANGE",
    "NAME_CHANGE_REQUIRES_REVIEW": "NAME_CHANGED",
}


class SupplierArticleReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SupplierArticleReviewRepository(session)

    async def sync_delta(
        self,
        run: SupplierDeltaRun,
        delta_items: list[SupplierDeltaItem],
        previous_items: list[SupplierSnapshotItem],
        current_items: list[SupplierSnapshotItem],
    ) -> None:
        previous = {item.id: item for item in previous_items}
        current = {item.id: item for item in current_items}
        additions: list[object] = []
        now = datetime.now(UTC)

        for delta in delta_items:
            prior = (
                previous.get(delta.previous_snapshot_item_id)
                if delta.previous_snapshot_item_id
                else None
            )
            latest = (
                current.get(delta.current_snapshot_item_id)
                if delta.current_snapshot_item_id
                else None
            )
            data = (
                latest.mapped_data if latest else (prior.mapped_data if prior else {})
            )
            product_code = str(
                data.get("product_code")
                or delta.change_summary.get("first_product_code")
                or delta.matching_key_value
            ).strip()
            ean = (
                str(data.get("ean") or delta.change_summary.get("ean") or "").strip()
                or None
            )

            if self._requires_review(delta):
                review = SupplierArticleReview(
                    id=uuid.uuid4(),
                    supplier_id=run.supplier_id,
                    source_connection_id=run.source_connection_id,
                    delta_run_id=run.id,
                    delta_item_id=delta.id,
                    product_code=product_code,
                    ean=ean,
                    status="PENDING_REVIEW",
                    severity=self._severity(delta),
                    issue_codes=self._issue_codes(delta),
                    reviewed_fingerprint=delta.current_item_fingerprint,
                )
                additions.extend(
                    [
                        review,
                        SupplierArticleReviewEvent(
                            id=uuid.uuid4(),
                            review_id=review.id,
                            action="OPENED",
                            previous_status=None,
                            current_status="PENDING_REVIEW",
                            actor_id="system",
                            event_metadata={"delta_code": run.delta_code},
                        ),
                    ]
                )
                continue

            if latest is None or not product_code:
                continue
            for blocked in await self.repository.pending_for_product(
                run.source_connection_id, product_code
            ):
                if blocked.delta_item_id == delta.id:
                    continue
                previous_status = blocked.status
                blocked.status = "AUTO_RELEASED"
                blocked.decision_comment = "Dobavljač je dostavio ispravljene podatke."
                blocked.decided_by = "system"
                blocked.decided_at = now
                blocked.version += 1
                additions.append(
                    SupplierArticleReviewEvent(
                        id=uuid.uuid4(),
                        review_id=blocked.id,
                        action="AUTO_RELEASED",
                        previous_status=previous_status,
                        current_status=blocked.status,
                        actor_id="system",
                        comment=blocked.decision_comment,
                        event_metadata={
                            "corrected_delta_id": str(run.id),
                            "corrected_delta_item_id": str(delta.id),
                        },
                    )
                )

        if additions:
            await self.repository.add_all(additions)

    async def list_reviews(
        self,
        *,
        supplier_id: uuid.UUID | None,
        source_id: uuid.UUID | None,
        status: str | None,
        issue_code: str | None,
        severity: str | None,
        product_code: str | None,
        limit: int,
        offset: int,
    ) -> ArticleReviewList:
        rows, total = await self.repository.list_reviews(
            supplier_id=supplier_id,
            source_id=source_id,
            status=status,
            issue_code=issue_code,
            severity=severity,
            product_code=product_code,
            limit=limit,
            offset=offset,
        )
        items = [await self._read(row) for row in rows]
        return ArticleReviewList(items=items, total=total)

    async def get(self, review_id: uuid.UUID) -> ArticleReviewRead:
        row = await self.repository.detail(review_id)
        if row is None:
            supplier_error(
                404, "article_review_not_found", "Kontrola artikla nije pronađena"
            )
        return await self._read(row)

    async def events(
        self, review_id: uuid.UUID, *, limit: int, offset: int
    ) -> ArticleReviewEventList:
        if await self.repository.detail(review_id) is None:
            supplier_error(
                404, "article_review_not_found", "Kontrola artikla nije pronađena"
            )
        rows, total = await self.repository.events(
            review_id, limit=limit, offset=offset
        )
        return ArticleReviewEventList(
            items=[
                ArticleReviewEventRead.model_validate(event, from_attributes=True)
                for event in rows
            ],
            total=total,
        )

    async def decide(
        self,
        review_id: uuid.UUID,
        *,
        approved: bool,
        expected_version: int,
        comment: str,
    ) -> ArticleReviewRead:
        try:
            row = await self.repository.detail(review_id, lock=True)
            if row is None:
                supplier_error(
                    404, "article_review_not_found", "Kontrola artikla nije pronađena"
                )
            review = row[0]
            if review.status != "PENDING_REVIEW":
                supplier_error(
                    409, "article_review_already_decided", "Kontrola je već završena"
                )
            if review.version != expected_version:
                supplier_error(
                    409,
                    "article_review_version_conflict",
                    "Podatak je u međuvremenu promenjen",
                )
            status = "MANUALLY_APPROVED" if approved else "REJECTED"
            review.status = status
            review.decision_comment = comment.strip()
            review.decided_by = current_actor_id() or "system"
            review.decided_at = datetime.now(UTC)
            review.version += 1
            await self.repository.add_all(
                [
                    SupplierArticleReviewEvent(
                        id=uuid.uuid4(),
                        review_id=review.id,
                        action="APPROVED" if approved else "REJECTED",
                        previous_status="PENDING_REVIEW",
                        current_status=status,
                        actor_id=review.decided_by,
                        comment=review.decision_comment,
                    )
                ]
            )
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            supplier_error(
                409,
                "article_review_version_conflict",
                "Podatak je u međuvremenu promenjen",
            )
        return await self.get(review_id)

    async def _read(self, row: ReviewRow) -> ArticleReviewRead:
        review, delta, previous, current, supplier_name, source_name, delta_code = row
        fields = await self.repository.fields(delta.id)
        return ArticleReviewRead(
            id=review.id,
            supplier_id=review.supplier_id,
            supplier_name=supplier_name,
            source_connection_id=review.source_connection_id,
            source_name=source_name,
            delta_run_id=review.delta_run_id,
            delta_code=delta_code,
            delta_item_id=review.delta_item_id,
            product_code=review.product_code,
            ean=review.ean,
            status=review.status,
            severity=review.severity,
            issue_codes=review.issue_codes,
            previous_data=previous.mapped_data if previous else None,
            current_data=current.mapped_data if current else None,
            field_changes=[self._field_read(field) for field in fields],
            decision_comment=review.decision_comment,
            decided_by=review.decided_by,
            opened_at=review.opened_at,
            decided_at=review.decided_at,
            version=review.version,
        )

    @staticmethod
    def _requires_review(delta: SupplierDeltaItem) -> bool:
        summary = delta.change_summary
        return (
            summary.get("downstream_blocked") is True
            or summary.get("requires_manual_approval") is True
        )

    @staticmethod
    def _issue_codes(delta: SupplierDeltaItem) -> list[str]:
        codes = {
            ISSUE_CODES.get(flag, flag)
            for flag in delta.anomaly_flags
            if flag != "DOWNSTREAM_ITEM_BLOCKED"
        }
        classification = str(delta.change_summary.get("classification") or "").strip()
        if classification and not codes:
            codes.add(classification)
        return sorted(codes or {"MANUAL_REVIEW_REQUIRED"})

    @staticmethod
    def _severity(delta: SupplierDeltaItem) -> str:
        if "CURRENT_RECORD_INVALID" in delta.anomaly_flags:
            return "CRITICAL"
        return "HIGH"

    @staticmethod
    def _field_read(field: SupplierDeltaFieldChange) -> dict[str, object]:
        return {
            "field_path": field.field_path,
            "field_role": field.field_role,
            "change_type": field.change_type,
            "previous_value": field.previous_value_preview,
            "current_value": field.current_value_preview,
            "absolute_change": str(field.absolute_numeric_change)
            if field.absolute_numeric_change is not None
            else None,
            "percentage_change": str(field.percentage_numeric_change)
            if field.percentage_numeric_change is not None
            else None,
        }


__all__ = ["ISSUE_CODES", "SupplierArticleReviewService"]
