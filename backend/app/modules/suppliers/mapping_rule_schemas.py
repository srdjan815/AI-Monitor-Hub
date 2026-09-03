from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.limits import MAX_CONTENT_CHARS, MAX_DB_INTEGER
from app.modules.suppliers.enums import MappingTransformationType


class MappingRuleValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_field_id: uuid.UUID = Field(
        description="Postojeći aktivni Schema Field iz povezanog Schema Profile-a.",
    )
    target_attribute: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z][a-z0-9_.-]*$",
        description=(
            "Logički naziv ciljnog Catalog atributa; Catalog modul se ne pristupa."
        ),
    )
    required: bool = Field(
        default=False,
        description="Da li budući izvršni sloj mora proizvesti ciljnu vrednost.",
    )
    default_value: str | None = Field(
        default=None,
        max_length=MAX_CONTENT_CHARS,
        description=(
            "Opciona podrazumevana ili konstantna vrednost bez VARCHAR ograničenja."
        ),
    )
    transformation_type: MappingTransformationType = Field(
        default=MappingTransformationType.COPY,
        description="Deklarativna transformacija; u ovom poglavlju se ne izvršava.",
    )
    transformation_config: dict[str, object] | None = Field(
        default=None,
        max_length=50,
        description="Ograničena JSON konfiguracija za budući Chapter 3.5 izvršni sloj.",
    )
    validation_rule: str | None = Field(
        default=None,
        max_length=MAX_CONTENT_CHARS,
        description="Deklarativno pravilo validacije koje se ovde ne izvršava.",
    )
    priority: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Jedinstven redosled pravila unutar Mapping Profile-a.",
    )

    @model_validator(mode="after")
    def validate_transformation_configuration(self) -> Self:
        configured = {
            MappingTransformationType.CONCAT,
            MappingTransformationType.SPLIT,
            MappingTransformationType.REPLACE,
            MappingTransformationType.REGEX,
        }
        defaulted = {
            MappingTransformationType.DEFAULT_VALUE,
            MappingTransformationType.CONSTANT,
        }
        if self.transformation_type in configured and not self.transformation_config:
            raise ValueError("Izabrana transformacija zahteva configuration")
        if self.transformation_type in defaulted and self.default_value is None:
            raise ValueError("Izabrana transformacija zahteva default_value")
        if self.transformation_config is not None:
            try:
                encoded = json.dumps(self.transformation_config)
            except (TypeError, ValueError) as exc:
                raise ValueError("Transformation configuration nije JSON") from exc
            if len(encoded.encode()) > 65_536:
                raise ValueError("Transformation configuration je prevelika")
        return self


class MappingRuleCreate(MappingRuleValues):
    pass


class MappingRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimistic_version: int = Field(ge=1, le=MAX_DB_INTEGER)
    schema_field_id: uuid.UUID | None = None
    target_attribute: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    required: bool | None = None
    default_value: str | None = Field(default=None, max_length=MAX_CONTENT_CHARS)
    transformation_type: MappingTransformationType | None = None
    transformation_config: dict[str, object] | None = Field(
        default=None,
        max_length=50,
    )
    validation_rule: str | None = Field(default=None, max_length=MAX_CONTENT_CHARS)
    priority: int | None = Field(default=None, ge=1, le=MAX_DB_INTEGER)


class MappingRuleRead(MappingRuleValues):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mapping_profile_id: uuid.UUID
    is_active: bool
    optimistic_version: int
    created_at: datetime
    updated_at: datetime


class MappingRuleListResponse(BaseModel):
    items: list[MappingRuleRead]
    total: int


__all__ = [
    "MappingRuleCreate",
    "MappingRuleListResponse",
    "MappingRuleRead",
    "MappingRuleUpdate",
]
