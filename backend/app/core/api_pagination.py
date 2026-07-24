from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar

from fastapi import HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    paginate_revision_keyset,
    paginate_time_keyset,
)
from app.core.pagination import InvalidCursorError

RowT = TypeVar("RowT")


def require_cursor_mode(
    *,
    pagination: str | None,
    offset: int,
) -> None:
    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": ("Cursor pagination cannot use offset mode or offset"),
            },
        )


async def time_page(
    session: AsyncSession,
    response: Response,
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
) -> list[RowT]:
    try:
        page = await paginate_time_keyset(
            session,
            cursor=cursor,
            resource=resource,
            filters=filters,
            limit=limit,
            loader=loader,
            timestamp_of=timestamp_of,
            id_of=id_of,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc
    response.headers["X-Snapshot-At"] = page.snapshot_at.isoformat()
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return page.items


async def revision_page(
    response: Response,
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
) -> list[RowT]:
    try:
        page = await paginate_revision_keyset(
            cursor=cursor,
            resource=resource,
            filters=filters,
            limit=limit,
            loader=loader,
            revision_of=revision_of,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc
    response.headers["X-Snapshot-Revision"] = str(page.snapshot_revision)
    if page.next_cursor:
        response.headers["X-Next-Cursor"] = page.next_cursor
    return page.items


__all__ = ["require_cursor_mode", "revision_page", "time_page"]
