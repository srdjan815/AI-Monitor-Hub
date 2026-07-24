from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import MAX_DB_INTEGER
from app.modules.suppliers.enums import MappingProfileStatus


class MappingProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Naziv verzionisanog skupa pravila mapiranja.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Administrativni opis namene Mapping Profile-a.",
    )


class MappingProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimistic_version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana verzija zapisa za optimističko zaključavanje.",
    )
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class MappingProfileAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimistic_version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana optimistička verzija profila.",
    )


class MappingProfileClone(MappingProfileAction):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class MappingProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Jedinstveni identifikator verzije mapiranja.")
    mapping_code: str = Field(
        max_length=50,
        description="Nepromjenljiva interna oznaka formata MAP-000001.",
    )
    schema_profile_id: uuid.UUID = Field(
        description="Aktivna Schema Profile verzija čija polja se mapiraju.",
    )
    name: str = Field(description="Naziv Mapping Profile verzije.")
    description: str | None = Field(description="Administrativni opis profila.")
    version_number: int = Field(description="Redni broj istorijske verzije mapiranja.")
    status: MappingProfileStatus = Field(
        description="DRAFT, ACTIVE ili ARCHIVED status verzije.",
    )
    is_active: bool = Field(description="False označava soft-deleted istorijski zapis.")
    rule_count: int = Field(description="Broj aktivnih Mapping Rule zapisa.")
    optimistic_version: int = Field(
        description="Verzija zapisa za zaštitu od izgubljenih izmena.",
    )
    created_at: datetime
    updated_at: datetime


class MappingProfileListResponse(BaseModel):
    items: list[MappingProfileRead]
    total: int


__all__ = [
    "MappingProfileAction",
    "MappingProfileClone",
    "MappingProfileCreate",
    "MappingProfileListResponse",
    "MappingProfileRead",
    "MappingProfileUpdate",
]
