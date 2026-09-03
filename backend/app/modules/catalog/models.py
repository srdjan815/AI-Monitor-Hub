from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDMixin
from app.modules.catalog.enums import AttributeDataType, AttributeScope


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_categories_code"),
        UniqueConstraint("parent_id", "name", name="uq_categories_parent_name"),
        Index("ix_categories_parent_position", "parent_id", "position"),
        Index("ix_categories_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    attribute_links: Mapped[list[CategoryAttribute]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )
    products: Mapped[list[Product]] = relationship(back_populates="category")


class AttributeDefinition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attribute_definitions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_attribute_definitions_code"),
        UniqueConstraint("slug", name="uq_attribute_definitions_slug"),
        UniqueConstraint("api_name", name="uq_attribute_definitions_api_name"),
        UniqueConstraint(
            "internal_name", name="uq_attribute_definitions_internal_name"
        ),
        Index("ix_attribute_definitions_scope_active", "scope", "is_active"),
        Index("ix_attribute_definitions_group_order", "group_id", "default_sort_order"),
        Index(
            "ix_attribute_definitions_created_cursor",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "default_sort_order >= 0", name="default_sort_order_nonnegative"
        ),
        CheckConstraint(
            "confidence_threshold >= 0 AND confidence_threshold <= 1",
            name="confidence_threshold_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tooltip: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attribute_groups.id", ondelete="SET NULL")
    )
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AttributeScope.CATEGORY.value
    )
    storage_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ATTRIBUTE_VALUE"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    source_path: Mapped[str | None] = mapped_column(String(500))
    data_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AttributeDataType.TEXT.value
    )
    unit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    api_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    show_in_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_on_webshop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_in_mini_specification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    show_in_full_specification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allows_multiple: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    minimum_value: Mapped[float | None] = mapped_column(Numeric(24, 8))
    maximum_value: Mapped[float | None] = mapped_column(Numeric(24, 8))
    minimum_length: Mapped[int | None] = mapped_column(Integer)
    maximum_length: Mapped[int | None] = mapped_column(Integer)
    regex_pattern: Mapped[str | None] = mapped_column(Text)
    default_unit: Mapped[str | None] = mapped_column(String(80))
    accepted_units: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    default_value: Mapped[Any | None] = mapped_column(JSONB)
    validation_message: Mapped[str | None] = mapped_column(Text)
    filter_type: Mapped[str | None] = mapped_column(String(32))
    filter_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_compatibility_attribute: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    compatibility_type: Mapped[str | None] = mapped_column(String(120))
    compatibility_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    use_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_prompt: Mapped[str | None] = mapped_column(Text)
    normalization_prompt: Mapped[str | None] = mapped_column(Text)
    validation_prompt: Mapped[str | None] = mapped_column(Text)
    confidence_threshold: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False, default=0.8
    )
    examples: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    forbidden_values: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    deactivated_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    category_links: Mapped[list[CategoryAttribute]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan"
    )


class CategoryAttribute(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "category_attributes"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "attribute_id", name="uq_category_attributes_pair"
        ),
        Index("ix_category_attributes_order", "category_id", "position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_id_override: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attribute_groups.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_visible_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    show_on_webshop_override: Mapped[bool | None] = mapped_column(Boolean)
    show_in_mini_specification_override: Mapped[bool | None] = mapped_column(Boolean)
    show_in_full_specification_override: Mapped[bool | None] = mapped_column(Boolean)
    is_filter_override: Mapped[bool | None] = mapped_column(Boolean)
    filter_type_override: Mapped[str | None] = mapped_column(String(32))
    is_compatibility_override: Mapped[bool | None] = mapped_column(Boolean)
    compatibility_priority_override: Mapped[int | None] = mapped_column(Integer)
    ai_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules_override: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    category: Mapped[Category] = relationship(back_populates="attribute_links")
    attribute: Mapped[AttributeDefinition] = relationship(
        back_populates="category_links", lazy="selectin"
    )


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("code", name="uq_products_code"),
        UniqueConstraint("sku", name="uq_products_sku"),
        UniqueConstraint("ean", name="uq_products_ean"),
        Index("ix_products_category", "category_id"),
        Index("ix_products_status", "status"),
        Index("ix_products_active", "is_active"),
        Index("ix_products_brand", "brand"),
        Index("ix_products_created_cursor", "created_at", "id"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)

    sku: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ean: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mpn: Mapped[str | None] = mapped_column(String(255), nullable=True)

    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }

    category: Mapped[Category] = relationship(back_populates="products")


# Re-export the Product Attribute System models from the active Catalog model
# module so mapper discovery remains compatible with the established layout.
from app.modules.catalog.attribute_models import (  # noqa: E402, F401
    AttributeChangeEvent,
    AttributeGroup,
    AttributeNormalizationRule,
    AttributeOption,
    AttributeOptionAlias,
    ProductAttributeValue,
    ProductAttributeValueHistory,
)
from app.modules.catalog.platform_models import (  # noqa: E402, F401
    AttributeDependency,
    AttributeFamily,
    AttributeFamilyItem,
    AttributeFormula,
    AttributePromptVersion,
    AttributeTemplate,
    AttributeTemplateFamily,
    AttributeTemplateItem,
    CategoryAttributeFamily,
    CategoryAttributeTemplate,
)
