from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    TimeKeyset,
    encode_time_keyset,
    resolve_time_keyset,
)
from app.core.pagination import InvalidCursorError


async def list_keyset(
    session: AsyncSession,
    *,
    cursor: str | None,
    pagination: Literal["offset", "cursor"] | None,
    offset: int,
    resource: str,
    filters: dict[str, Any],
) -> TimeKeyset | None:
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        return None
    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": "Cursor pagination cannot use offset mode or offset",
            },
        )
    try:
        return await resolve_time_keyset(
            session,
            cursor=cursor,
            resource=resource,
            filters=filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc


def after_keyset(keyset: TimeKeyset) -> tuple[datetime, uuid.UUID] | None:
    if keyset.after_at is None or keyset.after_id is None:
        return None
    return keyset.after_at, keyset.after_id


def set_page_headers(
    response: Response,
    *,
    resource: str,
    filters: dict[str, Any],
    keyset: TimeKeyset,
    last_at: datetime | None,
    last_id: uuid.UUID | None,
) -> None:
    response.headers["X-Snapshot-At"] = keyset.snapshot_at.isoformat()
    if last_at is None or last_id is None:
        return
    response.headers["X-Next-Cursor"] = encode_time_keyset(
        resource=resource,
        filters=filters,
        after_at=last_at,
        after_id=last_id,
        snapshot_at=keyset.snapshot_at,
    )


__all__ = ["after_keyset", "list_keyset", "set_page_headers"]
