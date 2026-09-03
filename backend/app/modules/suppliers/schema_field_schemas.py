from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.limits import MAX_DB_INTEGER
from app.modules.suppliers.enums import SchemaFieldDataType

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class SchemaFieldValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_code: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
        description="Stabilna oznaka ulaznog polja unutar jedne verzije.",
    )
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Čitljiv naziv ulaznog polja.",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Opis značenja polja bez pravila mapiranja.",
    )
    position: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Jedinstvena logička pozicija polja u profilu.",
    )
    data_type: SchemaFieldDataType = Field(
        description="Očekivani tip metapodatka; vrednost se ovde ne parsira.",
    )
    required: bool = Field(
        default=False,
        description="Da li ulazna struktura mora sadržati polje.",
    )
    nullable: bool = Field(
        default=True,
        description="Da li prisutno polje sme imati null vrednost.",
    )
    default_value: str | None = Field(
        default=None,
        max_length=4000,
        description="Tekstualno opisana podrazumevana vrednost.",
    )
    max_length: int | None = Field(
        default=None,
        ge=1,
        le=1_000_000,
        description="Najveća očekivana dužina za tekstualne/binarne tipove.",
    )
    precision: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Ukupan broj cifara za DECIMAL tip.",
    )
    scale: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Broj decimalnih mesta za DECIMAL tip.",
    )
    example_value: str | None = Field(
        default=None,
        max_length=4000,
        description="Bezbedan reprezentativni primer, ne stvarni uvezeni podatak.",
    )
    path: str = Field(
        min_length=1,
        max_length=500,
        description="Logička lokacija poput kolone, XPath-a ili JSON putanje.",
    )
    is_key: bool = Field(
        default=False, description="Jedinstveno ključno polje profila."
    )
    is_identifier: bool = Field(
        default=False,
        description="Polje nosi identifikator dobavljačevog proizvoda.",
    )
    is_price: bool = Field(default=False, description="Polje predstavlja cenu.")
    is_quantity: bool = Field(default=False, description="Polje predstavlja količinu.")
    is_stock: bool = Field(
        default=False, description="Polje predstavlja stanje zalihe."
    )
    is_currency: bool = Field(default=False, description="Polje predstavlja valutu.")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or _CONTROL.search(normalized) or ".." in normalized:
            raise ValueError("Logička putanja nije ispravna")
        return normalized

    @model_validator(mode="after")
    def validate_constraints(self) -> Self:
        if self.required and self.nullable:
            raise ValueError("Obavezno polje ne može istovremeno biti nullable")
        length_types = {
            SchemaFieldDataType.STRING,
            SchemaFieldDataType.EMAIL,
            SchemaFieldDataType.URL,
            SchemaFieldDataType.PHONE,
            SchemaFieldDataType.ENUM,
            SchemaFieldDataType.BINARY,
        }
        if self.max_length is not None and self.data_type not in length_types:
            raise ValueError("max_length nije dozvoljen za izabrani tip")
        if self.data_type != SchemaFieldDataType.DECIMAL and (
            self.precision is not None or self.scale is not None
        ):
            raise ValueError("precision i scale su dozvoljeni samo za DECIMAL")
        if self.scale is not None and self.precision is None:
            raise ValueError("scale zahteva precision")
        if (
            self.scale is not None
            and self.precision is not None
            and self.scale > self.precision
        ):
            raise ValueError("scale ne može biti veći od precision")
        return self


class SchemaFieldCreate(SchemaFieldValues):
    pass


class SchemaFieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana optimistička verzija polja.",
    )
    field_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
    )
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    position: int | None = Field(default=None, ge=1, le=MAX_DB_INTEGER)
    data_type: SchemaFieldDataType | None = None
    required: bool | None = None
    nullable: bool | None = None
    default_value: str | None = Field(default=None, max_length=4000)
    max_length: int | None = Field(default=None, ge=1, le=1_000_000)
    precision: int | None = Field(default=None, ge=1, le=1000)
    scale: int | None = Field(default=None, ge=0, le=1000)
    example_value: str | None = Field(default=None, max_length=4000)
    path: str | None = Field(default=None, min_length=1, max_length=500)
    is_key: bool | None = None
    is_identifier: bool | None = None
    is_price: bool | None = None
    is_quantity: bool | None = None
    is_stock: bool | None = None
    is_currency: bool | None = None


class SchemaFieldRead(SchemaFieldValues):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schema_profile_id: uuid.UUID
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class SchemaFieldListResponse(BaseModel):
    items: list[SchemaFieldRead]
    total: int


__all__ = [
    "SchemaFieldCreate",
    "SchemaFieldListResponse",
    "SchemaFieldRead",
    "SchemaFieldUpdate",
]
