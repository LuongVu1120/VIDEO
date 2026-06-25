import os
import uuid
import aiofiles
import threading
import traceback
import sys
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.auth import get_current_user
from ...core.config import settings
from ...models.user import User
from ...models.job import Job
from ...workers.tasks import process_job_sync, register_cancel_flag

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/default-directions")
async def get_default_video_directions():
    """
    Danh sách kịch bản video mặc định khi người dùng không nhập mô tả.
    """
    from ...services.default_video_directions import (
        DEFAULT_VIDEO_DIRECTIONS,
        preview_default_for_variation,
    )
    return {
        "message": "Khi không nhập mô tả, mỗi video variation tự chọn một kịch bản phù hợp.",
        "directions": [
            {
                "key": d["key"],
                "label_vi": d["label_vi"],
                "prompt_vi": d["prompt_vi"],
            }
            for d in DEFAULT_VIDEO_DIRECTIONS
        ],
        "preview": {
            "variation_1": preview_default_for_variation(0),
            "variation_2": preview_default_for_variation(1),
        },
    }


@router.post("/upload")
async def upload_image(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    num_images: int = Form(2),
    generate_video: bool = Form(True),
    video_duration: int = Form(5),
    max_video_variations: int = Form(1),
    platforms: str = Form("instagram"),
    auto_post: bool = Form(False),
    ai_provider: str = Form("openai"),
    user_description: str = Form("", description="Mô tả yêu cầu / hướng sáng tạo từ người dùng"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    print("[Upload] Request received")
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are allowed")

    if num_images not in (0, 2, 4, 6):
        raise HTTPException(
            status_code=400,
            detail="num_images must be 0, 2, 4, or 6",
        )
    if num_images == 0 and not generate_video:
        raise HTTPException(
            status_code=400,
            detail="When num_images is 0, generate_video must be enabled",
        )

    video_duration = max(3, min(15, video_duration))
    max_video_variations = max(1, min(2, max_video_variations))

    if settings.COST_SAVE_MODE:
        max_video_variations = 1
        video_duration = min(video_duration, 5)

    # Save file
    file_ext = image.filename.split(".")[-1] if image.filename else "jpg"
    file_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    async with aiofiles.open(file_path, "wb") as f:
        content = await image.read()
        await f.write(content)

    # Create job record
    platforms_list = [p.strip() for p in platforms.split(",")]

    job = Job(
        user_id=current_user.id,
        original_image_path=file_path,
        num_images=num_images,
        generate_video=generate_video,
        video_duration=video_duration,
        platforms=platforms_list,
        auto_post=auto_post,
        ai_provider=ai_provider,
        status="queued",
        estimated_time_seconds=120 if num_images == 0 else 180,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    options = {
        "num_images": num_images,
        "generate_video": generate_video,
        "video_duration": video_duration,
        "max_video_variations": max_video_variations,
        "platforms": platforms_list,
        "auto_post": auto_post,
        "ai_provider": ai_provider,
        "user_description": user_description.strip()[:300],
    }

    # Pipeline chạy SAU khi HTTP response trả về (tránh fetch pending / khóa SQLite)
    job_id = job.id
    register_cancel_flag(job_id)

    def run_pipeline(jid, fpath, opts):
        try:
            print(f"[Pipeline] Starting sync pipeline for job {jid}")
            process_job_sync(jid, fpath, opts)
            print(f"[Pipeline] Completed sync pipeline for job {jid}")
        except Exception as e:
            print(f"[Pipeline] Fatal error for job {jid}: {e}")
            traceback.print_exc()

    def schedule_pipeline():
        threading.Thread(
            target=run_pipeline, args=(job_id, file_path, options), daemon=True
        ).start()

    background_tasks.add_task(schedule_pipeline)
    print(f"[Upload] Job {job_id} queued — pipeline will start after response")

    return {
        "job_id": job.id,
        "status": job.status,
        "estimated_time_seconds": job.estimated_time_seconds,
        "webhook_url": f"/api/v1/jobs/{job.id}/status",
    }
