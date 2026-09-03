from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class SupplierArticleReview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "supplier_article_reviews"
    __table_args__ = (
        UniqueConstraint(
            "delta_item_id", name="uq_supplier_article_reviews_delta_item"
        ),
        CheckConstraint(
            "status IN ('PENDING_REVIEW','MANUALLY_APPROVED','REJECTED','AUTO_RELEASED','SUPERSEDED')",
            name="supplier_article_reviews_status_valid",
        ),
        Index("ix_article_reviews_queue", "status", "opened_at", "id"),
        Index(
            "ix_article_reviews_supplier_status", "supplier_id", "status", "opened_at"
        ),
        Index(
            "ix_article_reviews_source_product",
            "source_connection_id",
            "product_code",
            "status",
        ),
        Index("ix_article_reviews_issue_codes", "issue_codes", postgresql_using="gin"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_sources.id", ondelete="RESTRICT"), nullable=False
    )
    delta_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_delta_runs.id", ondelete="RESTRICT"), nullable=False
    )
    delta_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_delta_items.id", ondelete="RESTRICT"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(String(500), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="PENDING_REVIEW"
    )
    severity: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="HIGH"
    )
    issue_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    reviewed_fingerprint: Mapped[str | None] = mapped_column(String(64))
    decision_comment: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(255))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class SupplierArticleReviewEvent(UUIDMixin, Base):
    __tablename__ = "supplier_article_review_events"
    __table_args__ = (
        Index(
            "ix_article_review_events_review_created", "review_id", "created_at", "id"
        ),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_article_reviews.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    current_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


__all__ = ["SupplierArticleReview", "SupplierArticleReviewEvent"]
