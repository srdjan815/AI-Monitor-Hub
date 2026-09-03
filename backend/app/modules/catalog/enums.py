from enum import StrEnum


class AttributeScope(StrEnum):
    GLOBAL = "GLOBAL"
    CATEGORY = "CATEGORY"
    SYSTEM = "SYSTEM"
    INTERNAL = "INTERNAL"


class AttributeDataType(StrEnum):
    TEXT = "TEXT"
    LONG_TEXT = "LONG_TEXT"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    URL = "URL"
    ENUM = "ENUM"
    MULTI_ENUM = "MULTI_ENUM"
    DIMENSION = "DIMENSION"
    WEIGHT = "WEIGHT"
    POWER = "POWER"
    CAPACITY = "CAPACITY"
    FREQUENCY = "FREQUENCY"
    JSON = "JSON"

    # Backwards-compatible API values.
    SELECT = "SELECT"
    MULTISELECT = "MULTISELECT"


class AttributeStorageKind(StrEnum):
    CORE_FIELD = "CORE_FIELD"
    RELATION = "RELATION"
    CATEGORY_PATH = "CATEGORY_PATH"
    ATTRIBUTE_VALUE = "ATTRIBUTE_VALUE"
    CONTENT_FIELD = "CONTENT_FIELD"


class AttributeStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    INACTIVE = "INACTIVE"


class FilterType(StrEnum):
    CHECKBOX = "CHECKBOX"
    RANGE = "RANGE"
    DROPDOWN = "DROPDOWN"
    MULTI_SELECT = "MULTI_SELECT"
    BOOLEAN = "BOOLEAN"
    COLOR = "COLOR"
    TEXT = "TEXT"


class NormalizationRuleType(StrEnum):
    EXACT = "EXACT"
    CASE_INSENSITIVE_EXACT = "CASE_INSENSITIVE_EXACT"
    REGEX = "REGEX"
    UNIT = "UNIT"
    ENUM_ALIAS = "ENUM_ALIAS"
    WHITESPACE = "WHITESPACE"
    CUSTOM_TEMPLATE = "CUSTOM_TEMPLATE"


class AttributeSourceType(StrEnum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    SCRAPER = "SCRAPER"
    AI = "AI"
    SYSTEM = "SYSTEM"
    API = "API"


class ValidationStatus(StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"


class ApprovalStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttributeHistoryAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEACTIVATED = "DEACTIVATED"
    NORMALIZED = "NORMALIZED"
