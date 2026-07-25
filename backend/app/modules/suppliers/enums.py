from enum import StrEnum


class SupplierStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SupplierContactType(StrEnum):
    GENERAL = "GENERAL"
    TECHNICAL = "TECHNICAL"
    COMMERCIAL = "COMMERCIAL"
    BILLING = "BILLING"
    OTHER = "OTHER"


class SupplierSourceType(StrEnum):
    API = "API"
    CSV = "CSV"
    EXCEL = "EXCEL"
    XML = "XML"
    FTP = "FTP"
    SFTP = "SFTP"
    HTTP = "HTTP"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    EMAIL = "EMAIL"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class SupplierSourceStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class SupplierSourceValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class SchemaProfileStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SchemaFieldDataType(StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIME = "TIME"
    UUID = "UUID"
    EMAIL = "EMAIL"
    URL = "URL"
    PHONE = "PHONE"
    JSON = "JSON"
    ENUM = "ENUM"
    BINARY = "BINARY"


class MappingProfileStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MappingTransformationType(StrEnum):
    NONE = "NONE"
    COPY = "COPY"
    DEFAULT_VALUE = "DEFAULT_VALUE"
    CONSTANT = "CONSTANT"
    CONCAT = "CONCAT"
    SPLIT = "SPLIT"
    TRIM = "TRIM"
    UPPERCASE = "UPPERCASE"
    LOWERCASE = "LOWERCASE"
    REPLACE = "REPLACE"
    REGEX = "REGEX"


class AcquisitionTriggerType(StrEnum):
    MANUAL = "MANUAL"
    API_REQUEST = "API_REQUEST"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class AcquisitionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AcquisitionRecordStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class AcquisitionIssueSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


__all__ = [
    "SupplierContactType",
    "SupplierSourceStatus",
    "SupplierSourceType",
    "SupplierSourceValidationStatus",
    "SupplierStatus",
]
