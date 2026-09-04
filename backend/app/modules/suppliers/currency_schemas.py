from __future__ import annotations

import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

CurrencySource = Literal["CONFIGURED", "PRICE_LIST"]
RateMode = Literal["FIXED", "MANUAL", "AUTOMATIC"]
ExtractionMethod = Literal["JSON_PATH", "CSS_SELECTOR", "XPATH", "REGEX"]
SUPPORTED_CURRENCIES = frozenset(
    {
        "RSD",
        "EUR",
        "USD",
        "HUF",
        "GBP",
        "CHF",
        "CAD",
        "AUD",
        "JPY",
        "CNY",
        "CZK",
        "PLN",
        "RON",
        "BGN",
        "BAM",
        "MKD",
        "ALL",
        "TRY",
    }
)


class CurrencySettingWrite(BaseModel):
    source_connection_id: uuid.UUID | None = None
    currency_code: str = Field(min_length=3, max_length=3)
    currency_source: CurrencySource = "CONFIGURED"
    rate_mode: RateMode
    automatic_source_url: AnyHttpUrl | None = Field(default=None, max_length=2000)
    extraction_method: ExtractionMethod = "JSON_PATH"
    extraction_expression: str | None = Field(
        default=None, min_length=1, max_length=1000
    )
    decimal_separator: Literal[".", ","] = "."
    daily_check_time: time = time(6, 0)
    max_rate_age_hours: int = Field(default=48, ge=1, le=8760)
    expected_version: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> str:
        normalized = str(value).strip().upper()
        if not normalized.isalpha() or not normalized.isascii():
            raise ValueError("Valuta mora biti ISO oznaka od tri ASCII slova")
        if normalized not in SUPPORTED_CURRENCIES:
            raise ValueError("Valuta nije na dozvoljenoj ISO 4217 listi")
        return normalized

    @model_validator(mode="after")
    def validate_mode(self) -> CurrencySettingWrite:
        if self.currency_code == "RSD" and self.rate_mode != "FIXED":
            raise ValueError("RSD mora koristiti fiksni kurs 1")
        if self.currency_code != "RSD" and self.rate_mode == "FIXED":
            raise ValueError("Fiksni kurs je dozvoljen samo za RSD")
        if self.rate_mode == "AUTOMATIC" and self.automatic_source_url is None:
            raise ValueError("Automatski kurs zahteva HTTPS adresu izvora")
        if self.rate_mode == "AUTOMATIC" and self.source_connection_id is None:
            raise ValueError("Automatski kurs zahteva konekciju dobavljača")
        if self.rate_mode == "AUTOMATIC" and not self.extraction_expression:
            raise ValueError("Automatski kurs zahteva izraz za pronalaženje vrednosti")
        if self.automatic_source_url and self.automatic_source_url.scheme != "https":
            raise ValueError("Automatski izvor kursa mora koristiti HTTPS")
        return self


class ExchangeRateCreate(BaseModel):
    rate_to_rsd: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    effective_at: datetime
    source_type: Literal["FIXED", "MANUAL", "AUTOMATIC"]
    evidence_checksum: str | None = Field(
        default=None, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    note: str = Field(min_length=3, max_length=2000)

    @field_validator("effective_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datum važenja mora sadržati vremensku zonu")
        return value


class ExchangeRateRead(BaseModel):
    id: uuid.UUID
    rate_to_rsd: Decimal
    effective_at: datetime
    status: str
    source_type: str
    evidence_checksum: str | None
    source_excerpt: str | None
    source_content_type: str | None
    note: str | None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrencySettingRead(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    source_connection_id: uuid.UUID | None
    source_name: str | None
    portal_supplier_code: str | None
    currency_code: str
    currency_source: str
    rate_mode: str
    automatic_source_url: str | None
    extraction_method: str
    extraction_expression: str | None
    decimal_separator: str
    daily_check_time: time
    next_check_at: datetime | None
    last_check_at: datetime | None
    last_check_status: str | None
    last_check_message: str | None
    max_rate_age_hours: int
    current_rate: Decimal | None
    current_rate_effective_at: datetime | None
    rate_status: str
    version: int


class CurrencySettingList(BaseModel):
    items: list[CurrencySettingRead]
    total: int


class MonitorCurrencyRead(BaseModel):
    currency_code: Literal["RSD"]
    rate_to_rsd: Decimal
    version: int


class CurrencyEventRead(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: str
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrencyEventList(BaseModel):
    items: list[CurrencyEventRead]
    total: int


class CurrencySourceTestRequest(BaseModel):
    source_connection_id: uuid.UUID
    source_url: AnyHttpUrl = Field(max_length=2000)
    extraction_method: ExtractionMethod
    extraction_expression: str = Field(min_length=1, max_length=1000)
    decimal_separator: Literal[".", ","] = "."

    @field_validator("source_url")
    @classmethod
    def require_https(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Izvor kursa mora koristiti HTTPS")
        return value


class CurrencySourceTestRead(BaseModel):
    rate_to_rsd: Decimal
    fetched_at: datetime
    source_excerpt: str
    evidence_checksum: str
    content_type: str
    previous_rate: Decimal | None
    difference_percent: Decimal | None


__all__ = [
    "CurrencyEventList",
    "CurrencySettingList",
    "CurrencySettingRead",
    "CurrencySettingWrite",
    "CurrencySourceTestRead",
    "CurrencySourceTestRequest",
    "ExchangeRateCreate",
    "ExchangeRateRead",
    "MonitorCurrencyRead",
]
