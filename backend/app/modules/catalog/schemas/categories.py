from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    position: int = Field(default=0, ge=0)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    position: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    parent_id: uuid.UUID | None
    position: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CategoryTree(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    parent_id: uuid.UUID | None
    position: int
    is_active: bool
    children: list["CategoryTree"] = Field(default_factory=list)


class CategoryList(BaseModel):
    items: list[CategoryRead]
    total: int
