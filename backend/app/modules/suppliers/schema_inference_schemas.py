from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.suppliers.schema_field_schemas import SchemaFieldRead
from app.modules.suppliers.schema_profile_schemas import SchemaProfileRead


class InferredSchemaFieldRead(BaseModel):
    field: SchemaFieldRead
    sample_values: list[str] = Field(max_length=10)
    confidence: float = Field(ge=0, le=1)


class SchemaInferenceRead(BaseModel):
    profile: SchemaProfileRead
    original_filename: str | None = None
    detected_format: str
    encoding: str | None = None
    delimiter: str | None = None
    header_row: int | None = None
    root_path: str | None = None
    item_path: str | None = None
    record_count: int
    sampled_record_count: int
    fields: list[InferredSchemaFieldRead]


__all__ = ["InferredSchemaFieldRead", "SchemaInferenceRead"]
