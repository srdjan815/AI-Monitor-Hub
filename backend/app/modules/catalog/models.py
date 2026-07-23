from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
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
        Index("ix_attribute_definitions_scope_active", "scope", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AttributeScope.CATEGORY.value
    )
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
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allows_multiple: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_visible_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules_override: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    category: Mapped[Category] = relationship(back_populates="products")
