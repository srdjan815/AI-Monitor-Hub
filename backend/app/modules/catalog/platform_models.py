from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin


class AttributeFamily(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_families"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_attribute_families_slug"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_attribute_families_order", "sort_order", "slug"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class AttributeFamilyItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_family_items"
    __table_args__ = (
        UniqueConstraint(
            "family_id",
            "attribute_definition_id",
            name="uq_attribute_family_items_pair",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )

    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_families.id", ondelete="CASCADE"), nullable=False
    )
    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AttributeTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_templates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_attribute_templates_slug"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_attribute_templates_active", "is_active", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attribute_templates.id", ondelete="RESTRICT")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class AttributeTemplateItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_template_items"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "attribute_definition_id",
            name="uq_attribute_template_items_pair",
        ),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_attribute_template_items_order", "template_id", "sort_order"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_templates.id", ondelete="CASCADE"), nullable=False
    )
    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attribute_families.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required_override: Mapped[bool | None] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AttributeTemplateFamily(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_template_families"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "family_id", name="uq_attribute_template_families_pair"
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_templates.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_families.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CategoryAttributeFamily(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "category_attribute_families"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "family_id", name="uq_category_attribute_families_pair"
        ),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_families.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CategoryAttributeTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "category_attribute_templates"
    __table_args__ = (
        UniqueConstraint(
            "category_id",
            "template_id",
            name="uq_category_attribute_templates_pair",
        ),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_templates.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AttributeFormula(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_formulas"
    __table_args__ = (
        UniqueConstraint("target_attribute_id", name="uq_attribute_formulas_target"),
    )

    target_attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    formula_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class AttributeDependency(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_attribute_id",
            "target_attribute_id",
            "dependency_type",
            name="uq_attribute_dependencies_rule",
        ),
        Index(
            "ix_attribute_dependencies_target",
            "target_attribute_id",
            "dependency_type",
        ),
    )

    source_attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AttributePromptVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "attribute_definition_id",
            "version_number",
            name="uq_attribute_prompt_versions_number",
        ),
        Index(
            "ix_attribute_prompt_versions_active",
            "attribute_definition_id",
            "is_active",
        ),
    )

    attribute_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    extraction_prompt: Mapped[str | None] = mapped_column(Text)
    normalization_prompt: Mapped[str | None] = mapped_column(Text)
    validation_prompt: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    negative_examples: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    normalization_examples: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    validation_examples: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
