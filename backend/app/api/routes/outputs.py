import asyncio
import os
import subprocess
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.database import get_db
from ...models.job import Job
from ...models.output import Output
from ...services.caption_writer import CaptionWriter
from ...services.image_generator import ImageGenerator

router = APIRouter()

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------

class UpdateCaptionBody(BaseModel):
    platform: str
    title: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    call_to_action: Optional[str] = None


class RegenerateImageBody(BaseModel):
    image_prompt: str
    negative_prompt: str = ""
    image_index: int = 0


class TrimVideoBody(BaseModel):
    start_sec: float = 0.0
    end_sec: float


class RegenerateCaptionBody(BaseModel):
    platform: str
    extra_instruction: str = ""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_output_or_404(job_id: str, db: AsyncSession) -> Output:
    result = await db.execute(select(Output).where(Output.job_id == job_id))
    output = result.scalar_one_or_none()
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")
    return output


# ---------------------------------------------------------------------------
# GET — existing endpoint
# ---------------------------------------------------------------------------

@router.get("/{job_id}")
async def get_output(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not yet completed")

    output = await _get_output_or_404(job_id, db)

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


# ---------------------------------------------------------------------------
# PATCH /outputs/{job_id}/captions — save manually edited caption
# ---------------------------------------------------------------------------

@router.patch("/{job_id}/captions")
async def update_caption(
    job_id: str,
    body: UpdateCaptionBody,
    db: AsyncSession = Depends(get_db),
):
    """Save a manually edited caption for a specific platform."""
    output = await _get_output_or_404(job_id, db)

    captions = dict(output.captions or {})
    platform_data = dict(captions.get(body.platform, {}))

    # Each platform stores {"en": {...}, "vi": {...}}
    # We edit the "en" (posted) version
    en = dict(platform_data.get("en", {}))
    if body.title is not None:
        en["title"] = body.title
    if body.caption is not None:
        en["caption"] = body.caption
    if body.hashtags is not None:
        en["hashtags"] = body.hashtags
    if body.call_to_action is not None:
        en["call_to_action"] = body.call_to_action

    platform_data["en"] = en
    captions[body.platform] = platform_data
    output.captions = captions

    await db.commit()
    return {"success": True, "platform": body.platform, "en": en}


# ---------------------------------------------------------------------------
# POST /outputs/{job_id}/regenerate-image — regenerate one image with edited prompt
# ---------------------------------------------------------------------------

@router.post("/{job_id}/regenerate-image")
async def regenerate_image(
    job_id: str,
    body: RegenerateImageBody,
    db: AsyncSession = Depends(get_db),
):
    """Re-generate a specific image slot using an edited prompt."""
    output = await _get_output_or_404(job_id, db)

    gen = ImageGenerator()
    new_images = await asyncio.to_thread(
        gen.generate_images,
        prompt=body.image_prompt,
        negative=body.negative_prompt,
        n=1,
    )

    if not new_images:
        raise HTTPException(status_code=500, detail="Image generation returned no results")

    images = list(output.images or [])
    idx = body.image_index
    if idx < len(images):
        images[idx] = new_images[0]
    else:
        images.append(new_images[0])

    output.images = images
    await db.commit()

    return {"success": True, "image_url": new_images[0], "image_index": idx}


# ---------------------------------------------------------------------------
# POST /outputs/{job_id}/trim-video — trim video start/end with FFmpeg
# ---------------------------------------------------------------------------

@router.post("/{job_id}/trim-video")
async def trim_video(
    job_id: str,
    body: TrimVideoBody,
    db: AsyncSession = Depends(get_db),
):
    """Trim the generated video to a specific time range."""
    output = await _get_output_or_404(job_id, db)

    if not output.video_url:
        raise HTTPException(status_code=400, detail="No video available to trim")

    if body.end_sec <= body.start_sec:
        raise HTTPException(status_code=400, detail="end_sec must be greater than start_sec")

    # Resolve local path: /output/... → project_root/output/...
    video_url = output.video_url
    if not video_url.startswith("/output/"):
        raise HTTPException(
            status_code=422,
            detail="Video trim is only available for locally generated videos (paths starting with /output/)."
        )

    src_path = str(_PROJECT_ROOT / video_url.lstrip("/"))
    if not os.path.exists(src_path):
        raise HTTPException(status_code=404, detail=f"Video file not found at: {src_path}")

    out_dir = _PROJECT_ROOT / "output" / "trimmed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"{job_id}_{uuid.uuid4().hex[:8]}.mp4"
    out_path = str(out_dir / out_filename)

    duration = body.end_sec - body.start_sec
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(body.start_sec),
        "-i", src_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy", "-pix_fmt", "yuv420p",
        out_path,
    ]

    try:
        proc = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, timeout=120
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="replace"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video trim failed: {e}")

    new_url = f"/output/trimmed/{out_filename}"
    output.video_url = new_url
    await db.commit()

    return {
        "success": True,
        "video_url": new_url,
        "start_sec": body.start_sec,
        "end_sec": body.end_sec,
        "duration_sec": duration,
    }


# ---------------------------------------------------------------------------
# POST /outputs/{job_id}/regenerate-caption — re-generate caption with instruction
# ---------------------------------------------------------------------------

@router.post("/{job_id}/regenerate-caption")
async def regenerate_caption(
    job_id: str,
    body: RegenerateCaptionBody,
    db: AsyncSession = Depends(get_db),
):
    """Re-generate caption for a platform with an optional extra instruction."""
    output = await _get_output_or_404(job_id, db)

    style_data = output.style_analysis or {}

    writer = CaptionWriter(use_deepseek=settings.USE_DEEPSEEK_FOR_CAPTIONS)
    new_caption = await asyncio.to_thread(
        writer.write_bilingual_caption,
        style_data,
        body.platform,
        body.extra_instruction,
    )

    captions = dict(output.captions or {})
    captions[body.platform] = new_caption
    output.captions = captions
    await db.commit()

    return {"success": True, "platform": body.platform, "caption": new_caption}
