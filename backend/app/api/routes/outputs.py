from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...models.job import Job
from ...models.output import Output

router = APIRouter()


@router.get("/{job_id}")
async def get_output(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Verify job exists
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not yet completed")

    # Get output
    result = await db.execute(select(Output).where(Output.job_id == job_id))
    output = result.scalar_one_or_none()

    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    return {
        "job_id": job_id,
        "style_analysis": output.style_analysis,
        "variations": output.variations,
        "prompts": output.prompts,
        "images": output.images,
        "videos": output.videos or [],
        "video_url": output.video_url,
        "captions": output.captions,
        "music_suggestions": output.music_suggestions,
        "social_post_preview": output.social_post_preview,
        "cost_usd": output.cost_usd,
        "created_at": output.created_at.isoformat() if output.created_at else None,
    }
