from __future__ import annotations

from pydantic import BaseModel, Field


class MappingTestCell(BaseModel):
    source_field: str
    original_value: str | None
    target_attribute: str
    transformed_value: str | None
    status: str
    error: str | None = None


class MappingTestRow(BaseModel):
    row_number: int
    status: str
    cells: list[MappingTestCell]


class MappingTestRead(BaseModel):
    successful: bool
    tested_records: int
    warning_count: int
    error_count: int
    rows: list[MappingTestRow] = Field(max_length=10)
    message: str


__all__ = ["MappingTestCell", "MappingTestRead", "MappingTestRow"]
