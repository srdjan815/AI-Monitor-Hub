from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.limits import (
    BoundedJsonArray,
    BoundedJsonObject,
    BoundedJsonValue,
    MAX_BULK_ITEMS,
    MAX_COLLECTION_ITEMS,
    MAX_DB_INTEGER,
    MAX_DESCRIPTION_CHARS,
    MAX_NOTE_CHARS,
    MAX_PROMPT_CHARS,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NamedEntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


class NamedEntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    is_active: bool | None = None


class FamilyRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class FamilyItemCreate(BaseModel):
    attribute_definition_id: uuid.UUID
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    parent_template_id: uuid.UUID | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    parent_template_id: uuid.UUID | None = None
    is_active: bool | None = None


class TemplateRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    parent_template_id: uuid.UUID | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class TemplateItemCreate(BaseModel):
    attribute_definition_id: uuid.UUID
    family_id: uuid.UUID | None = None
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    is_required_override: bool | None = None


class TemplateImport(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    items: list[TemplateItemCreate] = Field(
        default_factory=list,
        max_length=MAX_BULK_ITEMS,
    )


class FormulaCreate(BaseModel):
    target_attribute_id: uuid.UUID
    formula_kind: str = Field(pattern="^(FORMULA|DERIVED)$")
    expression: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)


class FormulaUpdate(BaseModel):
    expression: str | None = Field(default=None, min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    is_active: bool | None = None


class FormulaRead(ORMModel):
    id: uuid.UUID
    target_attribute_id: uuid.UUID
    formula_kind: str
    expression: str
    description: str | None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class FormulaPreview(BaseModel):
    values: BoundedJsonObject = Field(default_factory=dict)


class DependencyCreate(BaseModel):
    source_attribute_id: uuid.UUID
    target_attribute_id: uuid.UUID
    dependency_type: str = Field(
        pattern="^(VISIBILITY|ALLOWED_VALUES|REQUIRED|DERIVATION)$"
    )
    rule_config: BoundedJsonObject = Field(default_factory=dict)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)

    @model_validator(mode="after")
    def distinct_attributes(self) -> DependencyCreate:
        if self.source_attribute_id == self.target_attribute_id:
            raise ValueError("A dependency cannot reference itself")
        return self


class DependencyRead(ORMModel):
    id: uuid.UUID
    source_attribute_id: uuid.UUID
    target_attribute_id: uuid.UUID
    dependency_type: str
    rule_config: dict[str, Any]
    description: str | None
    is_active: bool


class PromptVersionCreate(BaseModel):
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    extraction_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    normalization_prompt: str | None = Field(
        default=None,
        max_length=MAX_PROMPT_CHARS,
    )
    validation_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    negative_examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    normalization_examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    validation_examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    activate: bool = True


class PromptVersionRead(ORMModel):
    id: uuid.UUID
    attribute_definition_id: uuid.UUID
    version_number: int
    description: str | None
    extraction_prompt: str | None
    normalization_prompt: str | None
    validation_prompt: str | None
    examples: list[Any]
    negative_examples: list[Any]
    normalization_examples: list[Any]
    validation_examples: list[Any]
    is_active: bool
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LockRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)


class BulkProductChange(BaseModel):
    product_id: uuid.UUID
    attribute_id: uuid.UUID
    raw_value: BoundedJsonValue
    unit: str | None = Field(default=None, max_length=80)
    value_key: str = Field(default="single", min_length=1, max_length=64)


class EnterpriseBulkWrite(BaseModel):
    items: list[BulkProductChange] = Field(
        min_length=1,
        max_length=MAX_BULK_ITEMS,
    )

    @model_validator(mode="after")
    def no_duplicates(self) -> EnterpriseBulkWrite:
        keys = [
            (item.product_id, item.attribute_id, item.value_key) for item in self.items
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate product/attribute/value keys")
        return self
