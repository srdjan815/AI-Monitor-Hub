from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

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
    MAX_REGEX_CHARS,
)
from app.modules.catalog.enums import (
    ApprovalStatus,
    AttributeDataType,
    AttributeScope,
    AttributeSourceType,
    AttributeStatus,
    AttributeStorageKind,
    FilterType,
    NormalizationRuleType,
    ValidationStatus,
)

AcceptedUnit = Annotated[str, Field(min_length=1, max_length=80)]
OptionAlias = Annotated[str, Field(min_length=1, max_length=500)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AttributeGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)


class AttributeGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    is_active: bool | None = None


class AttributeGroupRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int = Field(ge=0, le=MAX_DB_INTEGER)


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(min_length=1, max_length=MAX_BULK_ITEMS)

    @model_validator(mode="after")
    def unique_ids(self) -> ReorderRequest:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate IDs are not allowed")
        return self


class AttributeDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    internal_name: str | None = Field(default=None, max_length=255)
    api_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    tooltip: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    group_id: uuid.UUID | None = None
    scope: AttributeScope = AttributeScope.CATEGORY
    storage_kind: AttributeStorageKind = AttributeStorageKind.ATTRIBUTE_VALUE
    data_type: AttributeDataType = AttributeDataType.TEXT
    status: AttributeStatus = AttributeStatus.ACTIVE
    source_path: str | None = Field(default=None, max_length=500)
    default_sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    show_in_admin: bool = True
    show_on_webshop: bool = True
    show_in_mini_specification: bool = False
    show_in_full_specification: bool = True
    is_searchable: bool = False
    is_required_by_default: bool = False
    allow_multiple_values: bool = False
    minimum_value: Decimal | None = Field(
        default=None,
        max_digits=24,
        decimal_places=8,
    )
    maximum_value: Decimal | None = Field(
        default=None,
        max_digits=24,
        decimal_places=8,
    )
    minimum_length: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    maximum_length: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    regex_pattern: str | None = Field(default=None, max_length=MAX_REGEX_CHARS)
    default_unit: str | None = Field(default=None, max_length=80)
    accepted_units: list[AcceptedUnit] = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    default_value: BoundedJsonValue | None = None
    validation_message: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
    )
    is_filter: bool = False
    filter_type: FilterType | None = None
    filter_sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    is_compatibility_attribute: bool = False
    compatibility_type: str | None = Field(default=None, max_length=120)
    compatibility_priority: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    use_ai: bool = False
    extraction_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    normalization_prompt: str | None = Field(
        default=None,
        max_length=MAX_PROMPT_CHARS,
    )
    validation_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    confidence_threshold: Decimal = Field(
        default=Decimal("0.8"),
        ge=0,
        le=1,
        max_digits=5,
        decimal_places=4,
    )
    examples: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )
    forbidden_values: BoundedJsonArray = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> AttributeDefinitionCreate:
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise ValueError("minimum_value must not exceed maximum_value")
        if (
            self.minimum_length is not None
            and self.maximum_length is not None
            and self.minimum_length > self.maximum_length
        ):
            raise ValueError("minimum_length must not exceed maximum_length")
        if self.is_filter and self.filter_type is None:
            raise ValueError("filter_type is required for filter attributes")
        if self.storage_kind in {
            AttributeStorageKind.CORE_FIELD,
            AttributeStorageKind.RELATION,
            AttributeStorageKind.CATEGORY_PATH,
        }:
            if self.allow_multiple_values:
                raise ValueError("system-backed attributes cannot be multi-value")
            if not self.source_path:
                raise ValueError("source_path is required for system-backed attributes")
        if self.data_type in {
            AttributeDataType.ENUM,
            AttributeDataType.MULTI_ENUM,
        } and self.storage_kind in {
            AttributeStorageKind.CORE_FIELD,
            AttributeStorageKind.RELATION,
            AttributeStorageKind.CATEGORY_PATH,
        }:
            raise ValueError("system-backed attributes cannot use enum storage")
        return self


class AttributeDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    tooltip: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    group_id: uuid.UUID | None = None
    status: AttributeStatus | None = None
    default_sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    show_in_admin: bool | None = None
    show_on_webshop: bool | None = None
    show_in_mini_specification: bool | None = None
    show_in_full_specification: bool | None = None
    is_searchable: bool | None = None
    is_required_by_default: bool | None = None
    minimum_value: Decimal | None = Field(
        default=None,
        max_digits=24,
        decimal_places=8,
    )
    maximum_value: Decimal | None = Field(
        default=None,
        max_digits=24,
        decimal_places=8,
    )
    minimum_length: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    maximum_length: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    regex_pattern: str | None = Field(default=None, max_length=MAX_REGEX_CHARS)
    default_unit: str | None = Field(default=None, max_length=80)
    accepted_units: list[AcceptedUnit] | None = Field(
        default=None,
        max_length=MAX_COLLECTION_ITEMS,
    )
    default_value: BoundedJsonValue | None = None
    validation_message: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
    )
    is_filter: bool | None = None
    filter_type: FilterType | None = None
    filter_sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    is_compatibility_attribute: bool | None = None
    compatibility_type: str | None = Field(default=None, max_length=120)
    compatibility_priority: int | None = Field(
        default=None,
        ge=0,
        le=MAX_DB_INTEGER,
    )
    use_ai: bool | None = None
    extraction_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    normalization_prompt: str | None = Field(
        default=None,
        max_length=MAX_PROMPT_CHARS,
    )
    validation_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_CHARS)
    confidence_threshold: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        max_digits=5,
        decimal_places=4,
    )
    examples: BoundedJsonArray | None = Field(
        default=None,
        max_length=MAX_COLLECTION_ITEMS,
    )
    forbidden_values: BoundedJsonArray | None = Field(
        default=None,
        max_length=MAX_COLLECTION_ITEMS,
    )
    is_active: bool | None = None


class AttributeDefinitionRead(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    internal_name: str
    api_name: str
    description: str | None
    tooltip: str | None
    group_id: uuid.UUID | None
    scope: str
    storage_kind: str
    data_type: str
    status: str
    source_path: str | None
    default_sort_order: int
    show_in_admin: bool
    show_on_webshop: bool
    show_in_mini_specification: bool
    show_in_full_specification: bool
    is_searchable: bool
    is_required: bool
    allows_multiple: bool
    minimum_value: Decimal | None
    maximum_value: Decimal | None
    minimum_length: int | None
    maximum_length: int | None
    regex_pattern: str | None
    default_unit: str | None
    accepted_units: list[str]
    default_value: Any | None
    validation_message: str | None
    is_filterable: bool
    filter_type: str | None
    filter_sort_order: int
    is_compatibility_attribute: bool
    compatibility_type: str | None
    compatibility_priority: int
    use_ai: bool
    extraction_prompt: str | None
    normalization_prompt: str | None
    validation_prompt: str | None
    confidence_threshold: Decimal
    examples: list[Any]
    forbidden_values: list[Any]
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CategoryAssignmentCreate(BaseModel):
    attribute_definition_id: uuid.UUID
    group_id_override: uuid.UUID | None = None
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    is_required_override: bool | None = None
    show_on_webshop_override: bool | None = None
    show_in_mini_specification_override: bool | None = None
    show_in_full_specification_override: bool | None = None
    is_filter_override: bool | None = None
    filter_type_override: FilterType | None = None
    is_compatibility_override: bool | None = None
    compatibility_priority_override: int | None = Field(
        default=None,
        ge=0,
        le=MAX_DB_INTEGER,
    )


class CategoryAssignmentUpdate(BaseModel):
    group_id_override: uuid.UUID | None = None
    sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    is_required_override: bool | None = None
    show_on_webshop_override: bool | None = None
    show_in_mini_specification_override: bool | None = None
    show_in_full_specification_override: bool | None = None
    is_filter_override: bool | None = None
    filter_type_override: FilterType | None = None
    is_compatibility_override: bool | None = None
    compatibility_priority_override: int | None = Field(
        default=None,
        ge=0,
        le=MAX_DB_INTEGER,
    )
    is_active: bool | None = None


class CategoryAssignmentRead(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    attribute_id: uuid.UUID
    group_id_override: uuid.UUID | None
    position: int
    is_required_override: bool | None
    show_on_webshop_override: bool | None
    show_in_mini_specification_override: bool | None
    show_in_full_specification_override: bool | None
    is_filter_override: bool | None
    filter_type_override: str | None
    is_compatibility_override: bool | None
    compatibility_priority_override: int | None
    is_active: bool
    version: int


class AttributeOptionCreate(BaseModel):
    canonical_value: str = Field(min_length=1, max_length=500)
    display_value: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    metadata: BoundedJsonObject = Field(default_factory=dict)
    aliases: list[OptionAlias] = Field(
        default_factory=list,
        max_length=MAX_COLLECTION_ITEMS,
    )


class AttributeOptionUpdate(BaseModel):
    display_value: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    metadata: BoundedJsonObject | None = None
    is_active: bool | None = None


class AttributeAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=500)


class AttributeAliasRead(ORMModel):
    id: uuid.UUID
    attribute_definition_id: uuid.UUID
    option_id: uuid.UUID
    alias: str


class AttributeOptionRead(ORMModel):
    id: uuid.UUID
    attribute_definition_id: uuid.UUID
    canonical_value: str
    display_value: str
    sort_order: int
    is_active: bool
    option_metadata: dict[str, Any]
    aliases: list[AttributeAliasRead] = Field(default_factory=list)


class NormalizationRuleCreate(BaseModel):
    rule_type: NormalizationRuleType
    pattern: str = Field(min_length=1, max_length=MAX_REGEX_CHARS)
    replacement: str | None = Field(default=None, max_length=MAX_REGEX_CHARS)
    priority: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    case_sensitive: bool = False
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)


class NormalizationRuleUpdate(BaseModel):
    pattern: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_REGEX_CHARS,
    )
    replacement: str | None = Field(default=None, max_length=MAX_REGEX_CHARS)
    priority: int | None = Field(default=None, ge=0, le=MAX_DB_INTEGER)
    case_sensitive: bool | None = None
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)


class NormalizationRuleRead(ORMModel):
    id: uuid.UUID
    attribute_definition_id: uuid.UUID
    rule_type: str
    pattern: str
    replacement: str | None
    priority: int
    case_sensitive: bool
    is_active: bool
    description: str | None


class ProductAttributeValueWrite(BaseModel):
    raw_value: BoundedJsonValue
    unit: str | None = Field(default=None, max_length=80)
    source_type: AttributeSourceType = AttributeSourceType.MANUAL
    source_reference: str | None = Field(default=None, max_length=500)
    confidence_score: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        max_digits=5,
        decimal_places=4,
    )
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    value_key: str = Field(default="single", min_length=1, max_length=64)
    position: int = Field(default=0, ge=0, le=MAX_DB_INTEGER)
    allow_invalid_for_review: bool = False


class ProductAttributeValueRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    attribute_definition_id: uuid.UUID
    value_key: str
    position: int
    raw_value: Any
    canonical_value: Any
    display_value: str
    unit: str | None
    source_type: str
    source_reference: str | None
    confidence_score: Decimal | None
    validation_status: str
    approval_status: str
    validation_message: str | None
    approved_by: str | None
    approved_at: datetime | None
    is_active: bool
    version: int
    is_locked: bool
    locked_by: str | None
    locked_at: datetime | None
    lock_reason: str | None
    created_at: datetime
    updated_at: datetime


class BulkValueItem(ProductAttributeValueWrite):
    attribute_id: uuid.UUID


class BulkValueWrite(BaseModel):
    items: list[BulkValueItem] = Field(
        min_length=1,
        max_length=MAX_BULK_ITEMS,
    )

    @model_validator(mode="after")
    def unique_values(self) -> BulkValueWrite:
        keys = [(item.attribute_id, item.value_key) for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate attribute/value keys are not allowed")
        return self


class ValidationResult(BaseModel):
    raw_value: Any
    canonical_value: Any | None
    display_value: str | None
    normalized_unit: str | None
    validation_status: ValidationStatus
    validation_messages: list[str]
    rules_applied: list[str]
    text_value: str | None = None
    numeric_value: Decimal | None = None
    boolean_value: bool | None = None
    date_value: date | None = None
    datetime_value: datetime | None = None
    json_value: Any | None = None


class ApprovalRequest(BaseModel):
    actor: str | None = Field(default=None, max_length=255)
    reason: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)


class ChangeEventRead(ORMModel):
    cursor: int
    entity_type: str
    entity_id: uuid.UUID
    product_id: uuid.UUID | None
    action: str
    occurred_at: datetime
    event_metadata: dict[str, Any]


class ResolvedAttribute(BaseModel):
    definition: AttributeDefinitionRead
    assignment: CategoryAssignmentRead | None = None
    inherited_from_category_id: uuid.UUID | None = None
    group_id: uuid.UUID | None
    sort_order: int
    read_only: bool
    value: Any | None = None
    display_value: str | None = None


class ResolvedAttributePage(BaseModel):
    items: list[ResolvedAttribute]
    total: int
    limit: int
    next_cursor: str | None = None
    snapshot_cursor: int
    snapshot_at: datetime


class FilterMetadata(BaseModel):
    attribute_id: uuid.UUID
    api_name: str
    label: str
    data_type: str
    filter_type: str
    unit: str | None
    options: list[AttributeOptionRead] = Field(default_factory=list)
    minimum_value: Decimal | None
    maximum_value: Decimal | None
    sort_order: int
    allows_multiple: bool


class ProductExport(BaseModel):
    product: dict[str, Any]
    category_path: list[dict[str, Any]]
    attributes: list[ResolvedAttribute]
    cursor: int
