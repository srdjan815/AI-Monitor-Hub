"""Compatibility facade for supplier payload parsers."""

from app.modules.suppliers.source_parsers import (
    CsvParser,
    JsonParser,
    ParserRegistry,
    XmlParser,
    XlsxParser,
)

__all__ = ["CsvParser", "JsonParser", "ParserRegistry", "XmlParser", "XlsxParser"]
