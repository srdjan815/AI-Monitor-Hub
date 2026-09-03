import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keyset_pagination import (
    encode_time_keyset,
    resolve_time_keyset,
)
from app.core.limits import MAX_CURSOR_CHARS, MAX_LEGACY_OFFSET
from app.core.pagination import InvalidCursorError
from app.db.session import get_db
from app.modules.execution.schemas import JobCreate, JobList, JobRead
from app.modules.execution.service import JobService

router = APIRouter(prefix="/jobs", tags=["execution"])


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_job(
    payload: JobCreate,
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await JobService(session).enqueue(payload)
    return JobRead.model_validate(job)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await JobService(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRead.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await JobService(session).cancel(job_id)
    return JobRead.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobRead)
async def retry_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> JobRead:
    job = await JobService(session).retry(job_id)
    return JobRead.model_validate(job)


@router.get("", response_model=JobList)
async def list_jobs(
    response: Response,
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    queue: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=MAX_LEGACY_OFFSET),
    cursor: str | None = Query(default=None, max_length=MAX_CURSOR_CHARS),
    pagination: Literal["offset", "cursor"] | None = None,
    session: AsyncSession = Depends(get_db),
) -> JobList:
    cursor_mode = cursor is not None or pagination == "cursor"
    if not cursor_mode:
        rows, total = await JobService(session).list(
            status=status_filter,
            queue=queue,
            limit=limit,
            offset=offset,
        )
        return JobList(
            items=[JobRead.model_validate(row) for row in rows],
            total=total,
        )

    if pagination == "offset" or offset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CURSOR",
                "message": ("Cursor pagination cannot use offset mode or offset"),
            },
        )

    cursor_filters = {
        "status": status_filter,
        "queue": queue,
        "limit": limit,
        "pagination": "cursor",
        "order": "created_at_desc,id_desc",
    }
    try:
        keyset = await resolve_time_keyset(
            session,
            cursor=cursor,
            resource="execution.jobs",
            filters=cursor_filters,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(exc)},
        ) from exc

    rows, total = await JobService(session).list(
        status=status_filter,
        queue=queue,
        limit=limit + 1,
        offset=0,
        snapshot_at=keyset.snapshot_at,
        after=(
            (keyset.after_at, keyset.after_id)
            if keyset.after_at is not None and keyset.after_id is not None
            else None
        ),
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    response.headers["X-Snapshot-At"] = keyset.snapshot_at.isoformat()
    if has_more:
        last = rows[-1]
        response.headers["X-Next-Cursor"] = encode_time_keyset(
            resource="execution.jobs",
            filters=cursor_filters,
            after_at=last.created_at,
            after_id=last.id,
            snapshot_at=keyset.snapshot_at,
        )
    return JobList(items=[JobRead.model_validate(row) for row in rows], total=total)
