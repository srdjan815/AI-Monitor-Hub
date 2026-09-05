from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class EolSupplierPresenceRead(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    product_code: str
    last_seen_at: datetime
    is_currently_offered: bool


class EolCandidateRead(BaseModel):
    identity_key: str
    ean: str | None
    product_name: str | None
    last_seen_at: datetime
    inactive_days: int
    status: Literal["EOL_CANDIDATE", "MARKED_FOR_DEACTIVATION", "DEACTIVATED"] = (
        "EOL_CANDIDATE"
    )
    export_batch_code: str | None = None
    export_eligible: bool
    suppliers: list[EolSupplierPresenceRead]


class EolCandidateList(BaseModel):
    items: list[EolCandidateRead]
    total: int
    inactivity_months: int
    cutoff_at: datetime


class EolBatchCreate(BaseModel):
    identity_keys: list[Annotated[str, Field(min_length=1, max_length=600)]] = Field(
        min_length=1, max_length=500
    )
    inactivity_months: int = Field(default=6, ge=1, le=12)
    target_systems: list[
        Annotated[Literal["WEBSITE", "PANTHEON"], Field(max_length=8)]
    ] = Field(min_length=1, max_length=2)
    idempotency_key: str = Field(min_length=8, max_length=255)

    @field_validator("identity_keys", "target_systems")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Vrednosti se ne smeju ponavljati")
        return values


class EolBatchRead(BaseModel):
    id: uuid.UUID
    batch_code: str
    status: str
    inactivity_months: int
    target_systems: list[str]
    item_count: int
    created_by: str
    created_at: datetime


__all__ = ["EolBatchCreate", "EolBatchRead", "EolCandidateList", "EolCandidateRead"]
