from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.enums import AttributeDataType, AttributeScope


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    position: int = Field(default=0, ge=0)
    is_active: bool = True
    description: str | None = None
    short_description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None
    brand: str | None = None
    sku: str | None = Field(default=None, max_length=100)
    ean: str | None = Field(default=None, max_length=50)
    weight: float | None = None
    dimensions: dict[str, Any] | None = None
    price: float | None = None
    currency: str = "RSD"
    stock_quantity: int = 0
    is_in_stock: bool = True
    attributes: dict[str, Any] = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: uuid.UUID | None = None
    position: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    description: str | None = None
    short_description: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None
    brand: str | None = None
    sku: str | None = Field(default=None, max_length=100)
    ean: str | None = Field(default=None, max_length=50)
    weight: float | None = None
    dimensions: dict[str, Any] | None = None
    price: float | None = None
    currency: str | None = None
    stock_quantity: int | None = None
    is_in_stock: bool | None = None
    attributes: dict[str, Any] | None = None
    images: list[str] | None = None
    videos: list[str] | None = None
    tags: list[str] | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    category_id: uuid.UUID | None
    position: int
    is_active: bool
    description: str | None
    short_description: str | None
    meta_title: str | None
    meta_description: str | None
    meta_keywords: str | None
    brand: str | None
    sku: str | None
    ean: str | None
    weight: float | None
    dimensions: dict[str, Any] | None
    price: float | None
    currency: str
    stock_quantity: int
    is_in_stock: bool
    attributes: dict[str, Any]
    images: list[str]
    videos: list[str]
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int