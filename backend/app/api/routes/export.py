"""
Multi-Format Export API.

POST /api/v1/export
  — Upload 1 video/ảnh 9:16, nhận về các format 1:1 và 16:9.

POST /api/v1/export/from-output
  — Export từ output của một job đã hoàn thành (truyền URL thay vì upload).
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...services.format_exporter import export_all_formats, get_format_urls
from ...services.watermark_service import add_image_watermark, add_video_watermark
from ...core.config import settings

router = APIRouter()

_BASE = Path(__file__).parent.parent.parent.parent.parent  # project root
UPLOAD_DIR = str(_BASE / "uploads" / "export")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".webm"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_ALL   = ALLOWED_VIDEO | ALLOWED_IMAGE


# ---------------------------------------------------------------------------
# Upload-based export
# ---------------------------------------------------------------------------

@router.post("/export", tags=["Export"])
async def export_formats_upload(
    file: UploadFile = File(..., description="Video hoặc ảnh 9:16 gốc"),
    formats: str = Form("1:1,16:9", description="Formats cần tạo, phân cách bằng dấu phẩy: 9:16,1:1,16:9"),
    apply_watermark: bool = Form(True, description="Áp dụng watermark thương hiệu"),
):
    """
    Upload 1 video/ảnh 9:16 → nhận về các format khác.

    Ví dụ: gửi video TikTok 9:16, nhận thêm 1:1 cho Instagram feed và 16:9 cho YouTube.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_ALL:
        raise HTTPException(400, detail=f"File không hỗ trợ: {ext}. Dùng mp4, jpg, png, webp.")

    # Parse formats
    requested = [f.strip() for f in formats.split(",") if f.strip() in ("9:16", "1:1", "16:9")]
    if not requested:
        raise HTTPException(400, detail="Không có format hợp lệ. Dùng: 9:16, 1:1, 16:9")

    # Save upload
    job_id = str(uuid.uuid4())
    src_path = os.path.join(UPLOAD_DIR, f"{job_id}_src{ext}")
    content = await file.read()
    with open(src_path, "wb") as f:
        f.write(content)

    # Export
    try:
        export_results = await asyncio.to_thread(
            export_all_formats, src_path, job_id, requested
        )
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
    except Exception as e:
        raise HTTPException(500, detail=f"Export error: {e}")

    # Apply watermark if requested
    if apply_watermark and settings.BRAND_NAME:
        is_vid = ext in ALLOWED_VIDEO
        watermarked: dict[str, str] = {}
        for fmt, path in export_results.items():
            try:
                wm_path = path.replace(ext, f"_wm{ext}")
                if is_vid:
                    wm = await asyncio.to_thread(
                        add_video_watermark, path,
                        settings.BRAND_NAME, settings.BRAND_PHONE,
                        settings.BRAND_WATERMARK_POSITION, wm_path,
                    )
                else:
                    wm = await asyncio.to_thread(
                        add_image_watermark, path,
                        settings.BRAND_NAME, settings.BRAND_PHONE,
                        settings.BRAND_WATERMARK_POSITION, wm_path,
                    )
                watermarked[fmt] = wm
            except Exception as e:
                print(f"[Export] Watermark {fmt} skipped: {e}")
                watermarked[fmt] = path
        export_results = watermarked

    urls = get_format_urls(export_results)

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "formats_created": list(export_results.keys()),
        "files": urls,
        "usage": {
            "9:16": "TikTok, Instagram Reels, YouTube Shorts",
            "1:1":  "Instagram Feed, Facebook post",
            "16:9": "YouTube, Facebook video cover",
        },
    })


# ---------------------------------------------------------------------------
# URL-based export (from existing job output)
# ---------------------------------------------------------------------------

class ExportFromOutputRequest(BaseModel):
    source_url: str
    formats: list[str] = ["1:1", "16:9"]
    apply_watermark: bool = True


@router.post("/export/from-output", tags=["Export"])
async def export_from_output_url(body: ExportFromOutputRequest):
    """
    Export từ URL của video/ảnh đã được tạo bởi pipeline.
    Tiện dụng khi muốn tạo thêm format từ output job cũ mà không upload lại.
    """
    import requests as req
    from pathlib import Path

    valid_formats = [f for f in body.formats if f in ("9:16", "1:1", "16:9")]
    if not valid_formats:
        raise HTTPException(400, detail="Không có format hợp lệ. Dùng: 9:16, 1:1, 16:9")

    # Download source
    try:
        resp = req.get(body.source_url, timeout=60, stream=True)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(400, detail=f"Không tải được file từ URL: {e}")

    content_type = resp.headers.get("content-type", "")
    ext = ".mp4" if "video" in content_type else ".jpg"

    job_id = str(uuid.uuid4())
    src_path = os.path.join(UPLOAD_DIR, f"{job_id}_src{ext}")
    with open(src_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

    try:
        export_results = await asyncio.to_thread(
            export_all_formats, src_path, job_id, valid_formats
        )
    except Exception as e:
        raise HTTPException(500, detail=f"Export error: {e}")

    if body.apply_watermark and settings.BRAND_NAME:
        is_vid = ext == ".mp4"
        for fmt, path in list(export_results.items()):
            try:
                wm_path = path.replace(ext, f"_wm{ext}")
                if is_vid:
                    export_results[fmt] = await asyncio.to_thread(
                        add_video_watermark, path,
                        settings.BRAND_NAME, settings.BRAND_PHONE,
                        settings.BRAND_WATERMARK_POSITION, wm_path,
                    )
                else:
                    export_results[fmt] = await asyncio.to_thread(
                        add_image_watermark, path,
                        settings.BRAND_NAME, settings.BRAND_PHONE,
                        settings.BRAND_WATERMARK_POSITION, wm_path,
                    )
            except Exception as e:
                print(f"[Export] Watermark {fmt} skipped: {e}")

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "source_url": body.source_url,
        "formats_created": list(export_results.keys()),
        "files": get_format_urls(export_results),
    })
