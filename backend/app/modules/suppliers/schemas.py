from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.limits import MAX_DB_INTEGER, MAX_DESCRIPTION_CHARS
from app.modules.suppliers.enums import SupplierContactType, SupplierStatus


_EMAIL_PATTERN = re.compile(
    r"^[^@\s]{1,64}@[^@\s.]{1,190}(?:\.[^@\s.]{1,63})+$",
    re.IGNORECASE,
)


class SupplierCreate(BaseModel):
    company_name: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Poslovni naziv dobavljača koji se prikazuje u Supplier Platformi."
        ),
    )
    address: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
        description="Poštanska ili poslovna adresa dobavljača.",
    )
    tax_identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description=(
            "Poreski identifikacioni broj dobavljača. Za dobavljače iz Srbije "
            "ovo je PIB."
        ),
    )
    registration_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Registracioni ili matični broj dobavljača.",
    )
    status: SupplierStatus = Field(
        default=SupplierStatus.ACTIVE,
        description=("Operativni status dobavljača. Ne predstavlja brisanje zapisa."),
    )


class SupplierUpdate(BaseModel):
    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description=(
            "Očekivana verzija zapisa koja sprečava prepisivanje paralelne izmene."
        ),
    )
    company_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Novi poslovni naziv dobavljača.",
    )
    address: str | None = Field(
        default=None,
        max_length=MAX_DESCRIPTION_CHARS,
        description="Nova adresa dobavljača ili null za uklanjanje adrese.",
    )
    tax_identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Novi poreski identifikacioni broj ili null za uklanjanje.",
    )
    registration_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Novi registracioni broj ili null za uklanjanje.",
    )
    status: SupplierStatus | None = Field(
        default=None,
        description="Novi operativni status dobavljača.",
    )


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        description="Jedinstveni interni identifikator dobavljača. Ne može se menjati."
    )
    supplier_code: str = Field(
        max_length=50,
        description=(
            "Jedinstvena interna šifra dobavljača koju automatski generiše sistem. "
            "Korisnik je ne može menjati."
        ),
    )
    company_name: str = Field(description="Poslovni naziv dobavljača.")
    address: str | None = Field(description="Adresa dobavljača.")
    tax_identifier: str | None = Field(
        description="Poreski identifikacioni broj dobavljača."
    )
    registration_number: str | None = Field(
        description="Registracioni ili matični broj dobavljača."
    )
    status: SupplierStatus = Field(description="Operativni status dobavljača.")
    is_active: bool = Field(
        description=(
            "Označava da li je zapis aktivan. Isključivanje je soft delete i ne "
            "briše istorijske podatke."
        )
    )
    version: int = Field(
        description=(
            "Verzija zapisa koja sprečava neprimetno prepisivanje paralelne izmene."
        )
    )
    created_at: datetime = Field(description="Vreme kreiranja zapisa.")
    updated_at: datetime = Field(description="Vreme poslednje izmene zapisa.")


class SupplierListResponse(BaseModel):
    items: list[SupplierRead] = Field(description="Dobavljači u trenutnoj stranici.")
    total: int = Field(description="Ukupan broj dobavljača za izabrane filtere.")


class SupplierContactCreate(BaseModel):
    contact_type: SupplierContactType = Field(
        default=SupplierContactType.GENERAL,
        description="Namena kontakta kod dobavljača.",
    )
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Ime i prezime kontakt osobe.",
    )
    email: str | None = Field(
        default=None,
        max_length=320,
        description="Normalizovana adresa elektronske pošte kontakt osobe.",
    )
    phone: str | None = Field(
        default=None,
        max_length=64,
        description="Broj telefona kontakt osobe.",
    )
    position: str | None = Field(
        default=None,
        max_length=255,
        description="Funkcija kontakt osobe kod dobavljača.",
    )
    is_primary: bool = Field(
        default=False,
        description="Označava glavni aktivni kontakt za izabranu vrstu kontakta.",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Email adresa nije ispravna")
        return normalized

    @model_validator(mode="after")
    def require_email_or_phone(self) -> SupplierContactCreate:
        if not (self.email and self.email.strip()) and not (
            self.phone and self.phone.strip()
        ):
            raise ValueError("Kontakt mora imati email ili telefon")
        return self


class SupplierContactUpdate(BaseModel):
    version: int = Field(
        ge=1,
        le=MAX_DB_INTEGER,
        description=(
            "Očekivana verzija kontakta koja sprečava prepisivanje paralelne izmene."
        ),
    )
    contact_type: SupplierContactType | None = Field(
        default=None,
        description="Nova namena kontakta.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Novo ime kontakt osobe.",
    )
    email: str | None = Field(
        default=None,
        max_length=320,
        description="Nova email adresa ili null za uklanjanje.",
    )
    phone: str | None = Field(
        default=None,
        max_length=64,
        description="Novi telefon ili null za uklanjanje.",
    )
    position: str | None = Field(
        default=None,
        max_length=255,
        description="Nova funkcija ili null za uklanjanje.",
    )
    is_primary: bool | None = Field(
        default=None,
        description="Određuje da li je ovo glavni kontakt izabrane vrste.",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Email adresa nije ispravna")
        return normalized


class SupplierContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Jedinstveni identifikator kontakta.")
    supplier_id: uuid.UUID = Field(description="Dobavljač kome kontakt pripada.")
    contact_type: SupplierContactType = Field(description="Namena kontakta.")
    name: str = Field(description="Ime kontakt osobe.")
    email: str | None = Field(description="Email adresa kontakt osobe.")
    phone: str | None = Field(description="Telefon kontakt osobe.")
    position: str | None = Field(description="Funkcija kontakt osobe.")
    is_primary: bool = Field(description="Označava glavni kontakt za izabranu vrstu.")
    is_active: bool = Field(
        description="Označava aktivan kontakt; false predstavlja soft delete."
    )
    version: int = Field(description="Verzija kontakta za optimističku konkurentnost.")
    created_at: datetime = Field(description="Vreme kreiranja kontakta.")
    updated_at: datetime = Field(description="Vreme poslednje izmene kontakta.")


class SupplierContactListResponse(BaseModel):
    items: list[SupplierContactRead] = Field(
        description="Kontakti u trenutnoj stranici."
    )
    total: int = Field(description="Ukupan broj kontakata za izabrane filtere.")


__all__ = [
    "SupplierContactCreate",
    "SupplierContactListResponse",
    "SupplierContactRead",
    "SupplierContactUpdate",
    "SupplierCreate",
    "SupplierListResponse",
    "SupplierRead",
    "SupplierUpdate",
]
