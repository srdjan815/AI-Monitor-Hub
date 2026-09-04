from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.limits import MAX_DB_INTEGER
from app.modules.suppliers.enums import (
    SupplierSourceStatus,
    SupplierSourceType,
    SupplierSourceValidationStatus,
)
from app.modules.suppliers.models import SupplierSource
from app.modules.suppliers.source_secrets import source_secret_provider

_REFERENCE_PATTERN = re.compile(
    r"^(?:(?:vault|env|secret):[A-Za-z0-9_./:-]+|supplier/[A-Za-z0-9_./-]+)$"
)


class SupplierSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Naziv izvora jedinstven među aktivnim izvorima dobavljača.",
    )
    source_type: SupplierSourceType = Field(
        description=(
            "Vrsta kanala preko kojeg dobavljač dostavlja podatke. "
            "Vrsta se ne može menjati nakon kreiranja izvora."
        )
    )
    configuration: dict[str, object] = Field(
        min_length=1,
        max_length=50,
        description=(
            "Podešavanja izvora prilagođena izabranoj vrsti konekcije. Lozinke, "
            "API ključevi i tokeni ne smeju se unositi u ovo polje."
        ),
    )
    secret_reference: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description=(
            "Referenca na poverljive podatke sačuvane van baze Supplier Platforme. "
            "Stvarna lozinka ili token se ne čuvaju u ovom zapisu."
        ),
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Administrativni opis namene izvora.",
    )
    portal_supplier_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
        description="Partnerska šifra dobavljača na ovom portalu.",
    )
    status: SupplierSourceStatus = Field(
        default=SupplierSourceStatus.DRAFT,
        description=(
            "Početni operativni status konfiguracije. Dozvoljeni su DRAFT i INACTIVE."
        ),
    )

    @field_validator("secret_reference")
    @classmethod
    def validate_secret_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not _REFERENCE_PATTERN.fullmatch(normalized):
            raise ValueError("Referenca na poverljive podatke nije ispravna")
        return normalized


class SupplierSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description="Očekivana verzija zapisa za optimističku konkurentnost.",
    )
    name: str | None = Field(default=None, min_length=1, max_length=255)
    configuration: dict[str, object] | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    secret_reference: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    portal_supplier_code: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"
    )
    status: SupplierSourceStatus | None = None
    source_type: SupplierSourceType | None = Field(
        default=None,
        description="Vrsta izvora je nepromenljiva i biće odbijena.",
    )

    @field_validator("secret_reference")
    @classmethod
    def validate_secret_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not _REFERENCE_PATTERN.fullmatch(normalized):
            raise ValueError("Referenca na poverljive podatke nije ispravna")
        return normalized


class SupplierSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Jedinstveni interni identifikator izvora.")
    supplier_id: uuid.UUID = Field(description="Dobavljač kome izvor pripada.")
    source_code: str = Field(
        max_length=50,
        description=(
            "Jedinstvena interna šifra izvora koju automatski generiše sistem. "
            "Korisnik je ne može menjati."
        ),
    )
    name: str
    source_type: SupplierSourceType
    status: SupplierSourceStatus = Field(
        description=(
            "Operativni status konfiguracije izvora. Status ne znači da je "
            "pokrenuto preuzimanje ili uvoz."
        )
    )
    is_active: bool = Field(description="Aktivnost zapisa; false predstavlja arhivu.")
    configuration: dict[str, object]
    has_secret_reference: bool = Field(
        description="Pokazuje da li postoji referenca bez otkrivanja njene vrednosti."
    )
    credentials_available: bool = Field(
        description=(
            "Pokazuje da li su referencirani pristupni podaci trenutno dostupni "
            "runtime provideru, bez otkrivanja reference ili vrednosti."
        )
    )
    description: str | None
    portal_supplier_code: str | None
    last_validation_at: datetime | None
    last_validation_status: SupplierSourceValidationStatus | None
    last_validation_message: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def resolve_runtime_credential_state(cls, value: object) -> object:
        if not isinstance(value, SupplierSource):
            return value
        return {
            field: getattr(value, field)
            for field in cls.model_fields
            if field != "credentials_available"
        } | {
            "credentials_available": source_secret_provider.available(
                value.secret_reference
            )
        }


class SupplierSourceListResponse(BaseModel):
    items: list[SupplierSourceRead]
    total: int


class SupplierSourceValidationResponse(BaseModel):
    valid: bool = Field(description="Da li je sačuvana konfiguracija ispravna.")
    status: SupplierSourceValidationStatus
    message: str = Field(
        description=(
            "Rezultat provere konfiguracije bez povezivanja sa spoljnim sistemom."
        )
    )
    validated_at: datetime
    version: int


__all__ = [
    "SupplierSourceCreate",
    "SupplierSourceListResponse",
    "SupplierSourceRead",
    "SupplierSourceUpdate",
    "SupplierSourceValidationResponse",
]
