from __future__ import annotations

from pydantic import BaseModel, Field


class SchemaRecordRead(BaseModel):
    record_number: int = Field(ge=1)
    manufacturer_code: str | None = None
    ean: str | None = None
    name: str | None = None
    price: str | None = None
    duplicate_count: int = Field(ge=1)
    values: dict[str, str | None]


class SchemaRecordListResponse(BaseModel):
    items: list[SchemaRecordRead]
    total: int = Field(ge=0)
    source_record_count: int = Field(ge=0)


__all__ = ["SchemaRecordListResponse", "SchemaRecordRead"]
