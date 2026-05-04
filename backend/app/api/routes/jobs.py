from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...models.job import Job

router = APIRouter()


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Parse steps_completed if stored as list
    steps_completed = job.steps_completed if isinstance(job.steps_completed, list) else []

    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "steps_completed": steps_completed,
        "estimated_remaining_seconds": job.estimated_remaining_seconds,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    result = await db.execute(
        select(Job)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    jobs = result.scalars().all()

    return [
        {
            "job_id": j.id,
            "status": j.status,
            "progress": j.progress,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
