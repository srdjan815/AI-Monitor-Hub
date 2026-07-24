from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import (
    BoundedJsonObject,
    MAX_DESCRIPTION_CHARS,
    MAX_PROMPT_CHARS,
)
from app.modules.catalog.enums import AttributeDataType, AttributeScope


class AttributeTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=255)
    scope: AttributeScope = AttributeScope.CATEGORY
    data_type: AttributeDataType = AttributeDataType.TEXT
    unit: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    ai_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    example_value: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
    )
    validation_rules: BoundedJsonObject = Field(default_factory=dict)
    api_name: str | None = Field(default=None, max_length=255)
    is_required: bool = False
    is_visible: bool = True
    is_filterable: bool = False
    is_searchable: bool = False
    allows_multiple: bool = False


class AttributeTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    data_type: AttributeDataType | None = None
    unit: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    ai_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    example_value: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
    )
    validation_rules: BoundedJsonObject | None = None
    api_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_required: bool | None = None
    is_visible: bool | None = None
    is_filterable: bool | None = None
    is_searchable: bool | None = None
    allows_multiple: bool | None = None
    is_active: bool | None = None


class AttributeTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    scope: str
    data_type: str
    unit: str | None
    description: str | None
    ai_prompt: str | None
    example_value: str | None
    validation_rules: dict[str, Any]
    api_name: str
    is_required: bool
    is_visible: bool
    is_filterable: bool
    is_searchable: bool
    allows_multiple: bool
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class AttributeTypeList(BaseModel):
    items: list[AttributeTypeRead]
    total: int
