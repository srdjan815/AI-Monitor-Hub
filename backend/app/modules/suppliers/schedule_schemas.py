from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.limits import MAX_DB_INTEGER

ScheduleStatus = Literal["MANUAL", "ENABLED", "PAUSED"]
ScheduleType = Literal["DAILY", "MULTI_DAILY", "INTERVAL", "WEEKDAYS", "WEEKLY"]
AutomationDepth = Literal["FETCH_ONLY", "FETCH_AND_ANALYZE", "FULL_PIPELINE"]


class SupplierScheduleWrite(BaseModel):
    version: int | None = Field(default=None, ge=1, le=MAX_DB_INTEGER)
    status: ScheduleStatus
    schedule_type: ScheduleType | None = None
    timezone: str = Field(default="Europe/Belgrade", min_length=1, max_length=100)
    times: list[Annotated[str, Field(min_length=5, max_length=5)]] = Field(
        default_factory=list,
        max_length=24,
    )
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    interval_hours: int | None = Field(default=None, ge=1, le=720)
    automation_depth: AutomationDepth = "FULL_PIPELINE"
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    max_attempts: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def validate_schedule(self) -> SupplierScheduleWrite:
        if self.status == "MANUAL":
            if self.schedule_type is not None:
                raise ValueError("RuÄni raspored ne koristi tip rasporeda")
            return self
        if self.schedule_type is None:
            raise ValueError("Izaberite tip rasporeda")
        if self.schedule_type == "INTERVAL":
            if self.interval_hours is None:
                raise ValueError("Unesite interval u satima")
        elif not self.times:
            raise ValueError("Unesite najmanje jedno vreme izvrÅ¡avanja")
        if self.schedule_type == "WEEKLY" and not self.weekdays:
            raise ValueError("Izaberite najmanje jedan dan u nedelji")
        return self

    def configuration(self) -> dict[str, object]:
        if self.schedule_type == "INTERVAL":
            return {"interval_hours": self.interval_hours}
        result: dict[str, object] = {"times": self.times}
        if self.schedule_type == "WEEKLY":
            result["weekdays"] = self.weekdays
        return result


class SupplierScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_connection_id: uuid.UUID
    status: ScheduleStatus
    schedule_type: ScheduleType | None
    timezone: str
    schedule_configuration: dict[str, object]
    automation_depth: AutomationDepth
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result: str | None
    last_duration_ms: int | None
    consecutive_failures: int
    timeout_seconds: int
    max_attempts: int
    version: int
    created_at: datetime
    updated_at: datetime


class SupplierScheduleListItem(SupplierScheduleRead):
    supplier_id: uuid.UUID
    supplier_name: str
    source_name: str
    source_code: str


class SupplierScheduleList(BaseModel):
    items: list[SupplierScheduleListItem]
    total: int


class PipelineRunNowRequest(BaseModel):
    automation_depth: AutomationDepth = "FULL_PIPELINE"
    idempotency_key: str = Field(min_length=1, max_length=255)


class PipelineRunQueued(BaseModel):
    pipeline_run_id: uuid.UUID
    pipeline_code: str
    job_id: uuid.UUID
    status: str
    automation_depth: AutomationDepth


__all__ = [
    "PipelineRunNowRequest",
    "PipelineRunQueued",
    "SupplierScheduleList",
    "SupplierScheduleListItem",
    "SupplierScheduleRead",
    "SupplierScheduleWrite",
]
