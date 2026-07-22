from enum import StrEnum


class AttributeScope(StrEnum):
    GLOBAL = "GLOBAL"
    CATEGORY = "CATEGORY"


class AttributeDataType(StrEnum):
    TEXT = "TEXT"
    LONG_TEXT = "LONG_TEXT"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    URL = "URL"
    SELECT = "SELECT"
    MULTISELECT = "MULTISELECT"
    JSON = "JSON"
