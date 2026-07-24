from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)

RowT = TypeVar("RowT")


@dataclass(frozen=True)
class TimeKeyset:
    after_at: datetime | None
    after_id: uuid.UUID | None
    snapshot_at: datetime


@dataclass(frozen=True)
class TimeKeysetPage(Generic[RowT]):
    items: list[RowT]
    snapshot_at: datetime
    next_cursor: str | None


@dataclass(frozen=True)
class RevisionKeysetPage(Generic[RowT]):
    items: list[RowT]
    snapshot_revision: int
    next_cursor: str | None


async def resolve_time_keyset(
    session: AsyncSession,
    *,
    cursor: str | None,
    resource: str,
    filters: dict[str, Any],
) -> TimeKeyset:
    if cursor is None:
        snapshot_at = await session.scalar(select(func.now()))
        if snapshot_at is None:
            raise InvalidCursorError("Could not establish a pagination snapshot")
        return TimeKeyset(
            after_at=None,
            after_id=None,
            snapshot_at=snapshot_at,
        )

    position = decode_cursor(cursor, resource, filters)
    if len(position) != 3:
        raise InvalidCursorError("Cursor position is invalid")
    after_at_value, after_id_value, snapshot_at_value = position
    if not all(
        isinstance(value, str)
        for value in (
            after_at_value,
            after_id_value,
            snapshot_at_value,
        )
    ):
        raise InvalidCursorError("Cursor position is invalid")
    assert isinstance(after_at_value, str)
    assert isinstance(after_id_value, str)
    assert isinstance(snapshot_at_value, str)

    try:
        after_at = datetime.fromisoformat(after_at_value)
        after_id = uuid.UUID(after_id_value)
        snapshot_at = datetime.fromisoformat(snapshot_at_value)
    except (TypeError, ValueError) as exc:
        raise InvalidCursorError("Cursor position is invalid") from exc
    if (
        after_at.tzinfo is None
        or after_at.utcoffset() is None
        or snapshot_at.tzinfo is None
        or snapshot_at.utcoffset() is None
    ):
        raise InvalidCursorError("Cursor timestamps must include a timezone")

    return TimeKeyset(
        after_at=after_at,
        after_id=after_id,
        snapshot_at=snapshot_at,
    )


def encode_time_keyset(
    *,
    resource: str,
    filters: dict[str, Any],
    after_at: datetime,
    after_id: uuid.UUID,
    snapshot_at: datetime,
) -> str:
    return encode_cursor(
        resource,
        filters,
        [
            after_at.isoformat(),
            str(after_id),
            snapshot_at.isoformat(),
        ],
    )


async def paginate_time_keyset(
    session: AsyncSession,
    *,
    cursor: str | None,
    resource: str,
    filters: dict[str, Any],
    limit: int,
    loader: Callable[
        [int, datetime, tuple[datetime, uuid.UUID] | None],
        Awaitable[list[RowT]],
    ],
    timestamp_of: Callable[[RowT], datetime],
    id_of: Callable[[RowT], uuid.UUID],
) -> TimeKeysetPage[RowT]:
    """Load one signed, snapshot-stable page ordered by time and UUID.

    The loader owns the ordering direction and must interpret ``after`` in the
    same direction encoded by ``filters["order"]``. Loading ``limit + 1``
    keeps continuation detection independent from a count query.
    """

    keyset = await resolve_time_keyset(
        session,
        cursor=cursor,
        resource=resource,
        filters=filters,
    )
    after = (
        (keyset.after_at, keyset.after_id)
        if keyset.after_at is not None and keyset.after_id is not None
        else None
    )
    rows = await loader(limit + 1, keyset.snapshot_at, after)
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_time_keyset(
            resource=resource,
            filters=filters,
            after_at=timestamp_of(last),
            after_id=id_of(last),
            snapshot_at=keyset.snapshot_at,
        )
    return TimeKeysetPage(
        items=items,
        snapshot_at=keyset.snapshot_at,
        next_cursor=next_cursor,
    )


async def paginate_revision_keyset(
    *,
    cursor: str | None,
    resource: str,
    filters: dict[str, Any],
    limit: int,
    loader: Callable[
        [int, int | None, int | None],
        Awaitable[tuple[list[RowT], int]],
    ],
    revision_of: Callable[[RowT], int],
) -> RevisionKeysetPage[RowT]:
    """Load a descending immutable revision page with a signed snapshot."""

    after_revision: int | None = None
    snapshot_revision: int | None = None
    if cursor is not None:
        position = decode_cursor(cursor, resource, filters)
        if (
            len(position) != 2
            or not isinstance(position[0], int)
            or not isinstance(position[1], int)
        ):
            raise InvalidCursorError("Cursor position is invalid")
        after_revision = position[0]
        snapshot_revision = position[1]
        if after_revision < 1 or snapshot_revision < after_revision:
            raise InvalidCursorError("Cursor revision range is invalid")

    rows, resolved_snapshot = await loader(
        limit + 1,
        after_revision,
        snapshot_revision,
    )
    if resolved_snapshot < 0:
        raise InvalidCursorError("Snapshot revision is invalid")
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(
            resource,
            filters,
            [revision_of(items[-1]), resolved_snapshot],
        )
    return RevisionKeysetPage(
        items=items,
        snapshot_revision=resolved_snapshot,
        next_cursor=next_cursor,
    )
