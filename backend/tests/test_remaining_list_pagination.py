from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    paginate_revision_keyset,
    paginate_time_keyset,
)
from app.core.pagination import InvalidCursorError
from app.main import app


@dataclass(frozen=True)
class _RevisionRow:
    id: uuid.UUID
    revision: int


@dataclass(frozen=True)
class _TimeRow:
    id: uuid.UUID
    occurred_at: datetime


class _SnapshotSession:
    def __init__(self, snapshot_at: datetime) -> None:
        self.snapshot_at = snapshot_at

    async def scalar(self, _statement: Any) -> datetime:
        return self.snapshot_at


@pytest.mark.asyncio
async def test_revision_cursor_is_snapshot_stable_and_filter_bound() -> None:
    rows = [
        _RevisionRow(id=uuid.UUID(int=revision), revision=revision)
        for revision in range(5, 0, -1)
    ]
    filters = {
        "content_key": str(uuid.uuid4()),
        "limit": 2,
        "order": "revision_desc",
    }

    async def loader(
        page_limit: int,
        after_revision: int | None,
        snapshot_revision: int | None,
    ) -> tuple[list[_RevisionRow], int]:
        snapshot = snapshot_revision or max(row.revision for row in rows)
        page = [row for row in rows if row.revision <= snapshot]
        if after_revision is not None:
            page = [row for row in page if row.revision < after_revision]
        return page[:page_limit], snapshot

    first = await paginate_revision_keyset(
        cursor=None,
        resource="test.revisions",
        filters=filters,
        limit=2,
        loader=loader,
        revision_of=lambda row: row.revision,
    )
    assert [row.revision for row in first.items] == [5, 4]
    assert first.snapshot_revision == 5
    assert first.next_cursor

    rows.insert(0, _RevisionRow(id=uuid.UUID(int=6), revision=6))
    second = await paginate_revision_keyset(
        cursor=first.next_cursor,
        resource="test.revisions",
        filters=filters,
        limit=2,
        loader=loader,
        revision_of=lambda row: row.revision,
    )
    assert [row.revision for row in second.items] == [3, 2]
    assert second.snapshot_revision == 5
    assert second.next_cursor

    final = await paginate_revision_keyset(
        cursor=second.next_cursor,
        resource="test.revisions",
        filters=filters,
        limit=2,
        loader=loader,
        revision_of=lambda row: row.revision,
    )
    assert [row.revision for row in final.items] == [1]
    assert final.next_cursor is None

    with pytest.raises(InvalidCursorError):
        await paginate_revision_keyset(
            cursor=first.next_cursor,
            resource="test.revisions",
            filters={**filters, "limit": 3},
            limit=3,
            loader=loader,
            revision_of=lambda row: row.revision,
        )


@pytest.mark.asyncio
async def test_time_cursor_handles_ties_without_duplicates_or_new_rows() -> None:
    snapshot = datetime(2026, 7, 24, 12, tzinfo=UTC)
    tied = snapshot - timedelta(minutes=2)
    rows = [
        _TimeRow(uuid.UUID(int=1), snapshot - timedelta(minutes=3)),
        _TimeRow(uuid.UUID(int=2), tied),
        _TimeRow(uuid.UUID(int=3), tied),
        _TimeRow(uuid.UUID(int=4), snapshot - timedelta(minutes=1)),
    ]
    rows.sort(key=lambda row: (row.occurred_at, row.id))
    filters = {
        "product_id": str(uuid.uuid4()),
        "limit": 2,
        "order": "occurred_at_asc,id_asc",
    }

    async def loader(
        page_limit: int,
        snapshot_at: datetime,
        after: tuple[datetime, uuid.UUID] | None,
    ) -> list[_TimeRow]:
        page = [row for row in rows if row.occurred_at <= snapshot_at]
        if after is not None:
            page = [row for row in page if (row.occurred_at, row.id) > after]
        return page[:page_limit]

    session = cast(AsyncSession, _SnapshotSession(snapshot))
    first = await paginate_time_keyset(
        session,
        cursor=None,
        resource="test.history",
        filters=filters,
        limit=2,
        loader=loader,
        timestamp_of=lambda row: row.occurred_at,
        id_of=lambda row: row.id,
    )
    assert first.next_cursor
    rows.append(_TimeRow(uuid.UUID(int=5), snapshot + timedelta(seconds=1)))

    second = await paginate_time_keyset(
        session,
        cursor=first.next_cursor,
        resource="test.history",
        filters=filters,
        limit=2,
        loader=loader,
        timestamp_of=lambda row: row.occurred_at,
        id_of=lambda row: row.id,
    )
    identifiers = [row.id for row in [*first.items, *second.items]]
    assert len(identifiers) == 4
    assert len(set(identifiers)) == 4
    assert uuid.UUID(int=5) not in identifiers


def test_known_collection_routes_expose_hard_limits() -> None:
    schema = app.openapi()
    expected = {
        "/api/v1/catalog/attribute-definitions",
        "/api/v1/catalog/products/{product_id}/attributes/history",
        "/api/v1/categories/{category_id}/attributes",
        "/api/v1/content/documents",
        "/api/v1/content/entries",
        "/api/v1/content/entries/{content_key}/history",
        "/api/v1/content/landing-pages",
        "/api/v1/content/landing-pages/{landing_key}/history",
        "/api/v1/content/library",
        "/api/v1/content/library/{item_id}/history",
        "/api/v1/content/products/{product_id}/score-history",
        "/api/v1/content/seo",
        "/api/v1/content/seo/{seo_key}/history",
        "/api/v1/content/types/{type_id}/prompts",
        "/api/v1/content/videos",
    }
    assert expected <= schema["paths"].keys()
    for path in expected:
        parameters = {
            parameter["name"]: parameter
            for parameter in schema["paths"][path]["get"]["parameters"]
            if parameter["in"] == "query"
        }
        assert "limit" in parameters, path
        maximum = parameters["limit"]["schema"].get("maximum")
        assert maximum is not None and maximum <= 500, path


def test_high_volume_lists_keep_additive_cursor_mode() -> None:
    schema = app.openapi()
    expected = {
        "/api/v1/catalog/attribute-definitions",
        "/api/v1/content/documents",
        "/api/v1/content/entries",
        "/api/v1/content/landing-pages",
        "/api/v1/content/library",
        "/api/v1/content/seo",
        "/api/v1/content/videos",
        "/api/v1/inventory",
        "/api/v1/inventory/movements",
        "/api/v1/inventory/reservations",
        "/api/v1/jobs",
        "/api/v1/products",
    }
    assert expected <= schema["paths"].keys()
    for path in expected:
        parameters = {
            parameter["name"]
            for parameter in schema["paths"][path]["get"]["parameters"]
            if parameter["in"] == "query"
        }
        assert {"cursor", "limit", "pagination"} <= parameters, path
