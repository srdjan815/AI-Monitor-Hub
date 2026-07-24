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


__all__ = [
    "SupplierContactType",
    "SupplierSourceStatus",
    "SupplierSourceType",
    "SupplierSourceValidationStatus",
    "SupplierStatus",
]
