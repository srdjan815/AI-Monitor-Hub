from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.limits import MAX_DB_INTEGER
from app.modules.suppliers.enums import SchemaProfileStatus


class SchemaProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Naziv logičke strukture podataka dobavljača.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Administrativni opis namene Schema Profile verzije.",
    )


class SchemaProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana optimistička verzija zapisa.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Novi naziv; dozvoljen je samo za DRAFT verziju.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Novi opis; dozvoljen je samo za DRAFT verziju.",
    )


class SchemaProfileAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana optimistička verzija profila.",
    )


class SchemaProfileClone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana verzija izvornog profila koji se klonira.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Opcioni naziv nove DRAFT verzije.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Opcioni opis nove DRAFT verzije.",
    )


class SchemaProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Jedinstveni identifikator verzije profila.")
    schema_code: str = Field(
        max_length=50,
        description="Nepromjenljiva interna oznaka formata SCH-000001.",
    )
    source_connection_id: uuid.UUID = Field(
        description="Source Connection čiju strukturu profil opisuje.",
    )
    name: str = Field(description="Naziv Schema Profile verzije.")
    description: str | None = Field(description="Administrativni opis profila.")
    version_number: int = Field(
        description="Redni broj nepromenljive istorijske verzije.",
    )
    status: SchemaProfileStatus = Field(
        description="DRAFT, ACTIVE ili ARCHIVED životni status verzije.",
    )
    is_active: bool = Field(
        description="False označava soft-deleted zapis koji ostaje u istoriji.",
    )
    field_count: int = Field(description="Broj aktivnih metadata polja u verziji.")
    detected_format: str | None = Field(
        description="Prepoznati format preuzetog cenovnika."
    )
    baseline_artifact_id: uuid.UUID | None = Field(
        description="Sačuvani originalni cenovnik iz kog je analiza nastala."
    )
    baseline_record_count: int | None = Field(
        description="Broj pronađenih proizvoda u preuzetom cenovniku."
    )
    last_analyzed_at: datetime | None = Field(
        description="Vreme poslednje uspešne analize cenovnika."
    )
    version: int = Field(description="Optimistička verzija samog zapisa.")
    created_at: datetime
    updated_at: datetime


class SchemaProfileListResponse(BaseModel):
    items: list[SchemaProfileRead]
    total: int


__all__ = [
    "SchemaProfileAction",
    "SchemaProfileClone",
    "SchemaProfileCreate",
    "SchemaProfileListResponse",
    "SchemaProfileRead",
    "SchemaProfileUpdate",
]
