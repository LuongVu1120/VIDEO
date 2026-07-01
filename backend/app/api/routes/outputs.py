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
from ...services.caption_utils import clamp_caption_fields, normalize_hashtags, CAPTION_MAX_HASHTAGS
from ...services.image_generator import ImageGenerator
from ...services.social_poster import SocialPoster

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


class PublishSocialBody(BaseModel):
    platform: str  # instagram | youtube


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _public_media_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = (settings.PUBLIC_MEDIA_BASE_URL or "http://127.0.0.1:8000").rstrip("/")
    if path.startswith("/"):
        return f"{base}{path}"
    return path


def _local_media_path(path: str | None) -> str | None:
    """Đường dẫn file local cho YouTube upload."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/output/"):
        local = _PROJECT_ROOT / path.lstrip("/")
        if local.exists():
            return str(local)
    uploads = _PROJECT_ROOT / "backend" / path
    if uploads.exists():
        return str(uploads)
    bare = _PROJECT_ROOT / "backend" / "uploads" / os.path.basename(path)
    if bare.exists():
        return str(bare)
    return None


def _pick_post_image(output: Output) -> str | None:
    for url in output.images or []:
        if url:
            return url
    return None


def _publish_sync(output: Output, platform: str) -> dict:
    captions = output.captions or {}
    # Fallback: youtube can use instagram caption if no dedicated youtube caption
    if platform not in captions:
        fallback = "instagram" if platform == "youtube" else None
        if fallback and fallback in captions:
            caption_data_fallback = captions[fallback]
        else:
            return {"status": "error", "error": f"No caption for platform: {platform}"}
    else:
        caption_data_fallback = None

    poster = SocialPoster()
    caption_data = caption_data_fallback if caption_data_fallback else captions[platform]
    image_path = _pick_post_image(output)
    video_path = output.video_url

    if platform == "youtube":
        if not video_path:
            return {"status": "error", "error": "Cần có video để đăng YouTube."}
        video_for_post = _local_media_path(video_path) or _public_media_url(video_path)
        if not video_for_post:
            return {"status": "error", "error": "Không tìm thấy file video."}
        return poster.post_to_platform(
            image_url="",
            video_url=video_for_post,
            caption_data=caption_data,
            platform="youtube",
            dry_run=False,
        )

    if platform == "instagram":
        pub_video = _public_media_url(video_path) if video_path else None
        pub_image = _public_media_url(image_path) if image_path else None
        if not pub_video and not pub_image:
            return {"status": "error", "error": "Cần ảnh hoặc video để đăng Instagram."}
        return poster.post_to_platform(
            image_url=pub_image or "",
            video_url=pub_video,
            caption_data=caption_data,
            platform="instagram",
            dry_run=False,
        )

    return {"status": "error", "error": f"Unsupported platform: {platform}"}


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
    video_error = None
    if job.generate_video and not output.video_url:
        video_error = job.error_message or (
            "Video generation was requested, but all video providers failed or returned no usable URL. "
            "Check backend logs for fal.ai / Google Veo / Runway errors."
        )

    return {
        "job_id": job_id,
        "style_analysis": output.style_analysis,
        "variations": output.variations,
        "prompts": output.prompts,
        "images": output.images,
        "videos": output.videos or [],
        "video_url": output.video_url,
        "video_requested": job.generate_video,
        "video_duration": job.video_duration,
        "video_error": video_error,
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
        en["hashtags"] = normalize_hashtags(body.hashtags, CAPTION_MAX_HASHTAGS)
    if body.call_to_action is not None:
        en["call_to_action"] = body.call_to_action

    en = clamp_caption_fields(en)
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


# ---------------------------------------------------------------------------
# POST /outputs/{job_id}/publish — đăng ngay lên Instagram / YouTube
# ---------------------------------------------------------------------------

@router.post("/{job_id}/publish")
async def publish_to_social(
    job_id: str,
    body: PublishSocialBody,
    db: AsyncSession = Depends(get_db),
):
    """Đăng bài lên Instagram hoặc YouTube (cần token OAuth trong .env)."""
    platform = body.platform.strip().lower()
    if platform not in ("instagram", "youtube"):
        raise HTTPException(status_code=400, detail="platform must be instagram or youtube")

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not yet completed")

    output = await _get_output_or_404(job_id, db)

    try:
        post_result = await asyncio.to_thread(_publish_sync, output, platform)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    status = post_result.get("status", "error")
    if status not in ("posted", "dry_run_ok"):
        raise HTTPException(
            status_code=502,
            detail=post_result.get("error") or post_result.get("note") or "Đăng bài thất bại",
        )

    preview = dict(output.social_post_preview or {})
    preview[platform] = post_result
    output.social_post_preview = preview
    await db.commit()

    return {
        "success": True,
        "platform": platform,
        "status": status,
        "post_url": post_result.get("post_url") or post_result.get("shorts_url"),
        "result": post_result,
    }
