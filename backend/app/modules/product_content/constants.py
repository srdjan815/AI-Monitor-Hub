from __future__ import annotations

from enum import StrEnum


class WorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    WAITING_REVIEW = "WAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ContentSource(StrEnum):
    MANUAL = "MANUAL"
    AI = "AI"
    SUPPLIER = "SUPPLIER"
    MANUFACTURER = "MANUFACTURER"
    SCRAPER = "SCRAPER"
    ERP = "ERP"
    IMPORT = "IMPORT"
    API = "API"
    SYSTEM = "SYSTEM"


class LibraryItemKind(StrEnum):
    BLOCK = "BLOCK"
    SNIPPET = "SNIPPET"
    SECTION = "SECTION"


class ConditionOperator(StrEnum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class ConditionComparator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GE = "GE"
    LT = "LT"
    LE = "LE"
    EXISTS = "EXISTS"


class PreviewMode(StrEnum):
    DESKTOP = "DESKTOP"
    TABLET = "TABLET"
    MOBILE = "MOBILE"
    RAW = "RAW"


class PreviewStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class LinkStatus(StrEnum):
    UNCHECKED = "UNCHECKED"
    OK = "OK"
    BROKEN = "BROKEN"
    REDIRECTED = "REDIRECTED"


class ScoreType(StrEnum):
    CONTENT = "CONTENT"
    SEO = "SEO"


DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 500
MAX_CHANGE_LIMIT = 1000
SEO_TITLE_MAX = 70
SEO_DESCRIPTION_MAX = 170
MAX_CONDITIONS_PER_ITEM = 64

BUILTIN_VARIABLES = frozenset(
    {"ProductName", "Manufacturer", "Brand", "SKU", "EAN", "MPN"}
)

DEFAULT_CONTENT_TYPES = (
    ("Short Description", "short_description"),
    ("Long Description", "long_description"),
    ("Marketing Description", "marketing_description"),
    ("Technical Description", "technical_description"),
    ("FAQ", "faq"),
    ("Highlights", "highlights"),
    ("Safety Notes", "safety_notes"),
    ("Warranty Notes", "warranty_notes"),
)

WORKFLOW_TRANSITIONS = {
    WorkflowStatus.DRAFT: {
        WorkflowStatus.WAITING_REVIEW,
        WorkflowStatus.ARCHIVED,
    },
    WorkflowStatus.WAITING_REVIEW: {
        WorkflowStatus.APPROVED,
        WorkflowStatus.REJECTED,
        WorkflowStatus.DRAFT,
    },
    WorkflowStatus.APPROVED: {
        WorkflowStatus.PUBLISHED,
        WorkflowStatus.ARCHIVED,
        WorkflowStatus.DRAFT,
    },
    WorkflowStatus.REJECTED: {
        WorkflowStatus.DRAFT,
        WorkflowStatus.ARCHIVED,
    },
    WorkflowStatus.PUBLISHED: {
        WorkflowStatus.ARCHIVED,
        WorkflowStatus.DRAFT,
    },
    WorkflowStatus.ARCHIVED: {WorkflowStatus.DRAFT},
}
