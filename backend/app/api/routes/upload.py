import os
import uuid
import aiofiles
import asyncio
import threading
import traceback
import sys
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.auth import get_current_user
from ...models.user import User
from ...models.job import Job
from ...workers.tasks import process_job_sync, register_cancel_flag

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_image(
    image: UploadFile = File(...),
    num_images: int = Form(2),
    generate_video: bool = Form(True),
    video_duration: int = Form(10),
    platforms: str = Form("instagram"),
    auto_post: bool = Form(False),
    ai_provider: str = Form("openai"),
    user_description: str = Form("", description="Mô tả yêu cầu / hướng sáng tạo từ người dùng"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are allowed")

    video_duration = max(3, min(15, video_duration))

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
        estimated_time_seconds=180,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    options = {
        "num_images": num_images,
        "generate_video": generate_video,
        "video_duration": video_duration,
        "platforms": platforms_list,
        "auto_post": auto_post,
        "ai_provider": ai_provider,
        "user_description": user_description.strip()[:300],
    }

    # Chay pipeline trong background thread (khong can Redis/Celery)
    job_id = job.id
    register_cancel_flag(job_id)

    def run_pipeline(jid, fpath, opts):
        try:
            print(f"[Pipeline] Starting sync pipeline for job {jid}")
            print(f"[Pipeline] file_path: {fpath}")
            print(f"[Pipeline] options: {opts}")
            process_job_sync(jid, fpath, opts)
            print(f"[Pipeline] Completed sync pipeline for job {jid}")
        except Exception as e:
            print(f"[Pipeline] Fatal error for job {jid}: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_pipeline, args=(job_id, file_path, options), daemon=True)
    thread.start()
    print(f"[Pipeline] Thread started for job {job_id}")

    return {
        "job_id": job.id,
        "status": job.status,
        "estimated_time_seconds": job.estimated_time_seconds,
        "webhook_url": f"/api/v1/jobs/{job.id}/status",
    }
