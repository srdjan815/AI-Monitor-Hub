import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.execution.repository import JobRepository
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


@router.get("", response_model=JobList)
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    queue: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> JobList:
    rows, total = await JobRepository(session).list(
        status=status_filter, queue=queue, limit=limit, offset=offset
    )
    return JobList(items=[JobRead.model_validate(row) for row in rows], total=total)
