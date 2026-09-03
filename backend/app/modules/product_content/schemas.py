from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.limits import (
    BoundedJsonArray,
    BoundedJsonObject,
    MAX_COLLECTION_ITEMS,
    MAX_CONTENT_CHARS,
    MAX_DB_INTEGER,
    MAX_DESCRIPTION_CHARS,
    MAX_NOTE_CHARS,
    MAX_PROMPT_CHARS,
)
from app.modules.product_content.constants import (
    ConditionComparator,
    ConditionOperator,
    ContentSource,
    LibraryItemKind,
    LinkStatus,
    PreviewMode,
    PreviewStatus,
    SEO_DESCRIPTION_MAX,
    SEO_TITLE_MAX,
    WorkflowStatus,
)

BoundedLabel = Annotated[str, Field(max_length=255)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LanguageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    native_name: str = Field(min_length=1, max_length=120)
    is_default: bool = False


class LanguageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    native_name: str | None = Field(default=None, min_length=1, max_length=120)
    is_default: bool | None = None


class LanguageRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    native_name: str
    is_default: bool
    is_active: bool


class ContentTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    supports_rich_text: bool = True
    is_multilanguage: bool = True


class ContentTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    supports_rich_text: bool | None = None
    is_multilanguage: bool | None = None


class ContentTypeRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    sort_order: int
    supports_rich_text: bool
    is_multilanguage: bool
    is_active: bool


class ContentWrite(BaseModel):
    language_id: uuid.UUID
    content_type_id: uuid.UUID
    title: str | None = Field(default=None, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    summary: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    approval_status: WorkflowStatus = WorkflowStatus.DRAFT
    source_type: ContentSource = ContentSource.MANUAL
    source_reference: str | None = Field(default=None, max_length=500)
    source_metadata: BoundedJsonObject = Field(default_factory=dict)
    created_by: str | None = Field(default=None, max_length=255)
    prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    prompt_version: str | None = Field(default=None, max_length=100)
    ai_model: str | None = Field(default=None, max_length=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    token_count: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    confidence: float | None = Field(default=None, ge=0, le=1)
    generation_time_ms: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    generation_reason: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)
    generation_notes: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    campaign: str | None = Field(default=None, max_length=255)
    priority: int = Field(default=0, ge=-MAX_DB_INTEGER, le=MAX_DB_INTEGER)

    @field_validator("publish_at", "expire_at")
    @classmethod
    def require_aware_schedule(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return value


class ContentRead(ORMModel):
    id: uuid.UUID
    content_key: uuid.UUID
    product_id: uuid.UUID
    language_id: uuid.UUID
    content_type_id: uuid.UUID
    title: str | None
    subtitle: str | None
    content: str
    summary: str | None
    status: str
    approval_status: str
    source_type: str
    source_reference: str | None
    source_metadata: dict[str, Any]
    revision: int
    is_current: bool
    created_by: str | None
    approved_by: str | None
    published_at: datetime | None
    publish_at: datetime | None
    expire_at: datetime | None
    campaign: str | None
    priority: int
    content_hash: str
    created_at: datetime
    updated_at: datetime


class WorkflowRequest(BaseModel):
    actor: str | None = Field(default=None, max_length=255)
    status: WorkflowStatus


class SEOWrite(BaseModel):
    language_id: uuid.UUID
    seo_title: str = Field(min_length=1, max_length=SEO_TITLE_MAX)
    seo_description: str = Field(
        min_length=1,
        max_length=SEO_DESCRIPTION_MAX,
    )
    seo_keywords: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    canonical_url: str | None = Field(default=None, max_length=1000)
    slug: str = Field(min_length=1, max_length=255)
    robots: str = Field(default="index,follow", max_length=120)
    open_graph: BoundedJsonObject = Field(default_factory=dict)
    twitter_card: BoundedJsonObject = Field(default_factory=dict)
    schema_org: BoundedJsonObject = Field(default_factory=dict)


class LandingWrite(BaseModel):
    language_id: uuid.UUID
    campaign: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    slug: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    hero_text: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    cta_text: str | None = Field(default=None, max_length=255)
    cta_url: str | None = Field(default=None, max_length=1000)
    meta: BoundedJsonObject = Field(default_factory=dict)
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    priority: int = Field(default=0, ge=-MAX_DB_INTEGER, le=MAX_DB_INTEGER)

    @field_validator("publish_at", "expire_at")
    @classmethod
    def require_aware_schedule(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return value


class ReferenceWrite(BaseModel):
    language_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=1500)
    reference_type: str = Field(min_length=1, max_length=40)
    version: str | None = Field(default=None, max_length=120)
    thumbnail_reference: str | None = Field(default=None, max_length=1500)
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


class LinkCheckWrite(BaseModel):
    status: LinkStatus
    error: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)
    checked_at: datetime | None = None
    next_check_at: datetime | None = None

    @field_validator("checked_at", "next_check_at")
    @classmethod
    def require_aware_check_time(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timezone-aware datetime required")
        return value


class RollbackRequest(BaseModel):
    revision: int = Field(ge=1, le=MAX_DB_INTEGER)
    actor: str | None = Field(default=None, max_length=255)


class LibraryWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    item_kind: LibraryItemKind
    category: str | None = Field(default=None, max_length=120)
    tags: list[BoundedLabel] = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    language_id: uuid.UUID
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class LibraryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    tags: list[BoundedLabel] | None = Field(
        default=None,
        max_length=MAX_COLLECTION_ITEMS,
    )
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    status: str | None = Field(default=None, max_length=32)
    approval_status: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class TemplateWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    is_active: bool | None = None


class TemplateItemWrite(BaseModel):
    library_item_id: uuid.UUID
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    condition_operator: ConditionOperator | None = None
    condition_source: str | None = Field(default=None, max_length=255)
    condition_comparator: ConditionComparator | None = None
    condition_value: str | None = Field(default=None, max_length=500)


class TemplateConditionWrite(BaseModel):
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    boolean_operator: ConditionOperator = ConditionOperator.AND
    source: str = Field(min_length=1, max_length=255)
    comparator: ConditionComparator
    expected_value: str | None = Field(default=None, max_length=500)


class PreviewRequest(BaseModel):
    language_id: uuid.UUID
    viewport: PreviewMode = PreviewMode.DESKTOP
    status: PreviewStatus = PreviewStatus.DRAFT
    trusted_raw: bool = False


class ScoringPolicyWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    short_description_weight: int = Field(default=15, ge=0, le=MAX_DB_INTEGER)
    long_description_weight: int = Field(default=20, ge=0, le=MAX_DB_INTEGER)
    seo_weight: int = Field(default=20, ge=0, le=MAX_DB_INTEGER)
    landing_weight: int = Field(default=15, ge=0, le=MAX_DB_INTEGER)
    document_weight: int = Field(default=10, ge=0, le=MAX_DB_INTEGER)
    video_weight: int = Field(default=10, ge=0, le=MAX_DB_INTEGER)
    translation_weight: int = Field(default=10, ge=0, le=MAX_DB_INTEGER)
    mandatory_sections: list[BoundedLabel] = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )


class PromptWrite(BaseModel):
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    prompt: str = Field(max_length=MAX_PROMPT_CHARS)
    variables: list[BoundedLabel] = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    negative_examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
