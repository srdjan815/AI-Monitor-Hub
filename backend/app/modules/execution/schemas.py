from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=120)
    queue: str = Field(default="default", min_length=1, max_length=80)
    priority: int = Field(default=100, ge=0, le=1000)
    payload: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, max_length=255)
    correlation_id: uuid.UUID | None = None
    created_by: str | None = Field(default=None, max_length=120)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    queue: str
    priority: int
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    attempt: int
    max_attempts: int
    available_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    locked_at: datetime | None
    locked_by: str | None
    correlation_id: uuid.UUID
    idempotency_key: str | None
    error_code: str | None
    error_message: str | None
    created_by: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class JobList(BaseModel):
    items: list[JobRead]
    total: int


class BusinessEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    event_key: str
    aggregate_type: str | None
    aggregate_id: str | None
    payload: dict[str, Any]
    status: str
    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None
    created_at: datetime
    published_at: datetime | None
