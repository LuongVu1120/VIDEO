"""
Before/After Comparison Video API.

POST /api/v1/before-after
  — Upload 2 ảnh (trước + sau), nhận về video so sánh + caption song ngữ.

Query params:
  effect      : split | reveal | slideshow  (default: reveal)
  add_labels  : true | false                (default: true)
  gen_caption : true | false                (default: true)
  platform    : instagram | tiktok | facebook | youtube (default: instagram)
  duration    : 6 – 15 seconds             (default: 8, dùng cho split & reveal)
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Literal, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from ...services.before_after_service import (
    create_comparison_video,
    generate_before_after_caption,
)
from ...services.watermark_service import add_video_watermark
from ...core.config import settings

router = APIRouter()

_BASE = Path(__file__).parent.parent.parent.parent.parent  # project root
UPLOAD_DIR = str(_BASE / "uploads" / "before_after")
OUTPUT_DIR = str(_BASE / "output" / "before_after")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _save_upload(file: UploadFile, prefix: str) -> str:
    ext = (file.filename or "img.jpg").rsplit(".", 1)[-1].lower()
    path = os.path.join(UPLOAD_DIR, f"{prefix}_{uuid.uuid4()}.{ext}")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return path


@router.post("/before-after", tags=["Before/After"])
async def create_before_after_video(
    before: UploadFile = File(..., description="Ảnh TRƯỚC (hiện trạng)"),
    after: UploadFile  = File(..., description="Ảnh SAU (thiết kế/render)"),
    effect: str   = Form("reveal",    description="split | reveal | slideshow"),
    add_labels: bool   = Form(True,   description="Hiển thị nhãn BEFORE/AFTER"),
    gen_caption: bool  = Form(True,   description="Tự động tạo caption"),
    platform: str      = Form("instagram"),
    duration: int      = Form(8,      description="Độ dài video (giây), 6-15"),
):
    # --- Validate ---
    for img in (before, after):
        if img.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, detail=f"Chỉ chấp nhận JPEG, PNG, WebP. Nhận được: {img.content_type}")

    effect = effect if effect in ("split", "reveal", "slideshow") else "reveal"
    duration = max(6, min(15, duration))

    # --- Save uploads ---
    job_id = str(uuid.uuid4())
    before_path = await _save_upload(before, "before")
    after_path  = await _save_upload(after, "after")

    video_path = os.path.join(OUTPUT_DIR, f"{job_id}_{effect}.mp4")

    # --- Create video (run FFmpeg in thread to avoid blocking event loop) ---
    try:
        await asyncio.to_thread(
            create_comparison_video,
            before_path,
            after_path,
            video_path,
            effect,
            add_labels,
            duration,
        )
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=f"FFmpeg error: {e}")

    # --- Apply branding watermark if configured ---
    final_video_path = video_path
    if settings.BRAND_NAME:
        try:
            branded_path = video_path.replace(".mp4", "_branded.mp4")
            final_video_path = await asyncio.to_thread(
                add_video_watermark,
                video_path,
                settings.BRAND_NAME,
                settings.BRAND_PHONE,
                settings.BRAND_WATERMARK_POSITION,
                branded_path,
            )
        except Exception as e:
            print(f"[BeforeAfter] Watermark skipped: {e}")

    # --- Generate caption ---
    caption = {}
    if gen_caption:
        try:
            caption = await asyncio.to_thread(
                generate_before_after_caption, effect, platform
            )
        except Exception as e:
            print(f"[BeforeAfter] Caption generation skipped: {e}")

    # --- Build response ---
    # Serve via /output/... static files mounted in main.py
    relative = final_video_path.replace("\\", "/")
    video_url = f"/output/before_after/{os.path.basename(final_video_path)}"

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "effect": effect,
        "duration_seconds": duration,
        "video_url": video_url,
        "video_path": relative,
        "caption": caption,
        "platforms_ready": ["instagram", "tiktok", "facebook", "youtube"],
        "tip": (
            "Dùng /api/v1/schedule/from-job để lên lịch đăng video này lên các platform."
            if caption else ""
        ),
    })
