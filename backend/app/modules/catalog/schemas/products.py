from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    category_id: uuid.UUID

    name: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, min_length=1, max_length=255)

    sku: str | None = Field(default=None, min_length=1, max_length=255)
    ean: str | None = Field(default=None, min_length=8, max_length=32)
    mpn: str | None = Field(default=None, min_length=1, max_length=255)

    brand: str | None = Field(default=None, min_length=1, max_length=255)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=255)

    status: str = Field(default="DRAFT", min_length=1, max_length=32)
    is_active: bool = True


class ProductUpdate(BaseModel):
    category_id: uuid.UUID | None = None

    name: str | None = Field(default=None, min_length=1, max_length=500)

    sku: str | None = Field(default=None, min_length=1, max_length=255)
    ean: str | None = Field(default=None, min_length=8, max_length=32)
    mpn: str | None = Field(default=None, min_length=1, max_length=255)

    brand: str | None = Field(default=None, min_length=1, max_length=255)
    manufacturer: str | None = Field(default=None, min_length=1, max_length=255)

    status: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID

    name: str
    code: str

    sku: str | None
    ean: str | None
    mpn: str | None

    brand: str | None
    manufacturer: str | None

    status: str
    is_active: bool
    version: int

    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
