from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ArticleReviewDecision(BaseModel):
    expected_version: int = Field(ge=1, le=2_147_483_647)
    comment: str = Field(min_length=3, max_length=2000)


class ArticleReviewRead(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    source_connection_id: uuid.UUID
    source_name: str
    delta_run_id: uuid.UUID
    delta_code: str
    delta_item_id: uuid.UUID
    product_code: str
    ean: str | None
    status: str
    severity: str
    issue_codes: list[str]
    previous_data: dict[str, object] | None
    current_data: dict[str, object] | None
    field_changes: list[dict[str, object]]
    decision_comment: str | None
    decided_by: str | None
    opened_at: datetime
    decided_at: datetime | None
    version: int


class ArticleReviewList(BaseModel):
    items: list[ArticleReviewRead]
    total: int


class ArticleReviewEventRead(BaseModel):
    id: uuid.UUID
    action: str
    previous_status: str | None
    current_status: str
    actor_id: str
    comment: str | None
    event_metadata: dict[str, object]
    created_at: datetime


class ArticleReviewEventList(BaseModel):
    items: list[ArticleReviewEventRead]
    total: int


__all__ = [
    "ArticleReviewDecision",
    "ArticleReviewEventRead",
    "ArticleReviewEventList",
    "ArticleReviewList",
    "ArticleReviewRead",
]
