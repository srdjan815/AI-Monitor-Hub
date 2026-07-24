from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class Language(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_languages"
    __table_args__ = (
        UniqueConstraint("code", name="uq_content_languages_code"),
        UniqueConstraint("name", name="uq_content_languages_name"),
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    native_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentType(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_types"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_content_types_slug"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supports_rich_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_multilanguage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductContent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_contents"
    __table_args__ = (
        UniqueConstraint(
            "content_key", "revision", name="uq_product_contents_revision"
        ),
        Index(
            "ix_product_contents_lookup",
            "product_id",
            "language_id",
            "content_type_id",
            "is_current",
        ),
        Index("ix_product_contents_workflow", "status", "approval_status"),
        Index("ix_product_contents_updated", "updated_at"),
        Index(
            "uq_product_contents_current_key",
            "content_key",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        CheckConstraint(
            "expire_at IS NULL OR publish_at IS NULL OR expire_at > publish_at",
            name="schedule_order",
        ),
    )
    content_key: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT"), nullable=False
    )
    content_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_types.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500))
    subtitle: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MANUAL"
    )
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[str | None] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prompt: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    ai_model: Mapped[str | None] = mapped_column(String(120))
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    token_count: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    generation_time_ms: Mapped[int | None] = mapped_column(Integer)
    generation_reason: Mapped[str | None] = mapped_column(Text)
    generation_notes: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_contents.id", ondelete="SET NULL")
    )
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    campaign: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProductSEO(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_seo"
    __table_args__ = (
        UniqueConstraint("seo_key", "revision", name="uq_product_seo_revision"),
        Index("ix_product_seo_current", "product_id", "language_id", "is_current"),
        Index(
            "uq_product_seo_current_slug",
            "language_id",
            "slug",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index(
            "uq_product_seo_current_key",
            "seo_key",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
    seo_key: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT"), nullable=False
    )
    seo_title: Mapped[str] = mapped_column(String(70), nullable=False)
    seo_description: Mapped[str] = mapped_column(String(170), nullable=False)
    seo_keywords: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    robots: Mapped[str] = mapped_column(
        String(120), nullable=False, default="index,follow"
    )
    open_graph: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    twitter_card: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    schema_org: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    approved_by: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LandingPage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_landing_pages"
    __table_args__ = (
        UniqueConstraint("landing_key", "revision", name="uq_product_landing_revision"),
        Index("ix_product_landing_current", "product_id", "language_id", "is_current"),
        Index(
            "uq_product_landing_current_key",
            "landing_key",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        CheckConstraint(
            "expire_at IS NULL OR publish_at IS NULL OR expire_at > publish_at",
            name="schedule_order",
        ),
    )
    landing_key: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT"), nullable=False
    )
    campaign: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    hero_text: Mapped[str | None] = mapped_column(Text)
    cta_text: Mapped[str | None] = mapped_column(String(255))
    cta_url: Mapped[str | None] = mapped_column(String(1000))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DocumentReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_document_references"
    __table_args__ = (
        Index("ix_product_documents_product", "product_id", "language_id"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str | None] = mapped_column(String(120))
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MANUAL"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    link_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNCHECKED"
    )
    link_error: Mapped[str | None] = mapped_column(Text)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VideoReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_video_references"
    __table_args__ = (
        Index("ix_product_videos_product", "product_id", "language_id", "sort_order"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    video_type: Mapped[str] = mapped_column(String(40), nullable=False)
    thumbnail_reference: Mapped[str | None] = mapped_column(String(1500))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    link_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNCHECKED"
    )
    link_error: Mapped[str | None] = mapped_column(Text)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContentChangeEvent(UUIDMixin, Base):
    __tablename__ = "content_change_events"
    __table_args__ = (Index("ix_content_change_product", "product_id", "cursor"),)
    cursor: Mapped[int] = mapped_column(
        BigInteger, Identity(), unique=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ContentLibraryItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_library_items"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_content_library_items_slug"),
        Index("ix_content_library_kind_status", "item_kind", "status"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    item_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approval_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class ContentLibraryRevision(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_library_revisions"
    __table_args__ = (
        UniqueConstraint(
            "library_item_id", "revision", name="uq_content_library_revision"
        ),
        Index(
            "uq_content_library_current_language",
            "library_item_id",
            "language_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_library_items.id", ondelete="CASCADE"), nullable=False
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_languages.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductLibraryReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_library_references"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "library_item_id",
            name="uq_product_library_reference",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_product_library_item", "library_item_id", "is_active"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_library_items.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_templates"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class ContentTemplateItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_template_items"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "library_item_id",
            name="uq_content_template_item",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_templates.id", ondelete="CASCADE"), nullable=False
    )
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_library_items.id", ondelete="RESTRICT"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_operator: Mapped[str | None] = mapped_column(String(16))
    condition_source: Mapped[str | None] = mapped_column(String(255))
    condition_comparator: Mapped[str | None] = mapped_column(String(20))
    condition_value: Mapped[str | None] = mapped_column(String(500))


class ContentTemplateCondition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_template_conditions"
    __table_args__ = (
        Index(
            "ix_content_template_conditions_item",
            "template_item_id",
            "sort_order",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )
    template_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_template_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boolean_operator: Mapped[str] = mapped_column(
        String(16), nullable=False, default="AND"
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    comparator: Mapped[str] = mapped_column(String(20), nullable=False)
    expected_value: Mapped[str | None] = mapped_column(String(500))


class ProductContentTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "product_content_templates"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "template_id",
            name="uq_product_content_template",
        ),
        Index("ix_product_content_template", "template_id", "is_active"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_templates.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentScoringPolicy(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_scoring_policies"
    __table_args__ = (
        CheckConstraint(
            "short_description_weight >= 0 AND "
            "long_description_weight >= 0 AND seo_weight >= 0 AND "
            "landing_weight >= 0 AND document_weight >= 0 AND "
            "video_weight >= 0 AND translation_weight >= 0",
            name="weights_nonnegative",
        ),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    short_description_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    long_description_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20
    )
    seo_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    landing_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    document_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    video_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    translation_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    mandatory_sections: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContentScoreHistory(UUIDMixin, Base):
    __tablename__ = "content_score_history"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        Index(
            "ix_content_score_product_type_calculated",
            "product_id",
            "score_type",
            "calculated_at",
        ),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_scoring_policies.id", ondelete="SET NULL")
    )
    score_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ContentTypePromptVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "content_type_prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "content_type_id",
            "version",
            name="uq_content_type_prompt_version",
        ),
        Index(
            "ix_content_prompt_type_active",
            "content_type_id",
            "is_active",
        ),
        Index(
            "uq_content_prompt_active_type",
            "content_type_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )
    content_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_types.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    examples: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    negative_examples: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
