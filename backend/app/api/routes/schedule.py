"""
Content Calendar API — CRUD endpoints cho lịch đăng bài.

POST   /api/v1/schedule          — Tạo lịch đăng mới
GET    /api/v1/schedule          — Xem tất cả lịch đăng
GET    /api/v1/schedule/{id}     — Xem chi tiết 1 lịch
PATCH  /api/v1/schedule/{id}     — Đổi giờ đăng
DELETE /api/v1/schedule/{id}     — Huỷ lịch đăng
POST   /api/v1/schedule/from-job — Tạo lịch từ output của job đã generate xong
"""

from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from ...services.scheduler_service import (
    create_scheduled_post,
    list_scheduled_posts,
    get_scheduled_post,
    cancel_scheduled_post,
    reschedule_post,
)
from ...services.caption_utils import clamp_caption_fields

router = APIRouter()

VALID_PLATFORMS = {"instagram", "facebook", "tiktok", "youtube"}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CaptionSchema(BaseModel):
    title: str = ""
    caption: str = ""
    hashtags: list[str] = []
    call_to_action: str = ""


class CreateScheduleRequest(BaseModel):
    platform: Literal["instagram", "facebook", "tiktok", "youtube"]
    scheduled_at: datetime          # ISO 8601, e.g. "2026-05-15T19:00:00+07:00"
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    caption_en: CaptionSchema       # English caption — will be posted
    caption_vi: Optional[CaptionSchema] = None   # Vietnamese — shown in UI only
    job_id: Optional[str] = None    # Link to generation job (optional)

    @model_validator(mode="after")
    def media_required(self):
        has_image = bool(self.image_url and self.image_url.strip())
        has_video = bool(self.video_url and self.video_url.strip())
        if not has_image and not has_video:
            raise ValueError("image_url or video_url is required")
        if self.platform in {"youtube", "tiktok"} and not has_video:
            raise ValueError(f"{self.platform} requires video_url")
        return self


class RescheduleRequest(BaseModel):
    scheduled_at: datetime


class CreateFromJobRequest(BaseModel):
    """Create multiple scheduled posts from a completed job's output in one call."""
    job_id: str
    platforms: list[Literal["instagram", "facebook", "tiktok", "youtube"]]
    scheduled_at: datetime          # same time for all platforms
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    captions: dict                  # {"instagram": {"en":{...}, "vi":{...}}, ...}

    @model_validator(mode="after")
    def media_required(self):
        has_image = bool(self.image_url and self.image_url.strip())
        has_video = bool(self.video_url and self.video_url.strip())
        if not has_image and not has_video:
            raise ValueError("image_url or video_url is required")
        video_platforms = {"youtube", "tiktok"}.intersection(self.platforms)
        if video_platforms and not has_video:
            names = ", ".join(sorted(video_platforms))
            raise ValueError(f"{names} require video_url")
        return self


def _post_to_dict(post) -> dict:
    return {
        "id": post.id,
        "platform": post.platform,
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat(),
        "image_url": post.image_url,
        "video_url": post.video_url,
        "caption_en": post.caption_en,
        "caption_vi": post.caption_vi,
        "job_id": post.job_id,
        "post_result": post.post_result,
        "error_message": post.error_message,
        "created_at": post.created_at.isoformat(),
        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/schedule", status_code=201, tags=["Schedule"])
def create_schedule(body: CreateScheduleRequest):
    """Tạo 1 lịch đăng bài cho 1 platform."""
    post = create_scheduled_post(
        platform=body.platform,
        scheduled_at=body.scheduled_at,
        image_url=body.image_url,
        video_url=body.video_url,
        caption_en=clamp_caption_fields(body.caption_en.model_dump()),
        caption_vi=clamp_caption_fields(body.caption_vi.model_dump()) if body.caption_vi else {},
        job_id=body.job_id,
    )
    return {"success": True, "scheduled_post": _post_to_dict(post)}


@router.post("/schedule/from-job", status_code=201, tags=["Schedule"])
def create_schedule_from_job(body: CreateFromJobRequest):
    """
    Tạo lịch đăng cho nhiều platform cùng lúc từ output của 1 job.
    Tiện dụng khi user muốn đăng cùng 1 nội dung lên Instagram + Facebook + TikTok
    vào cùng 1 thời điểm.
    """
    created = []
    for platform in body.platforms:
        platform_captions = body.captions.get(platform, {})
        caption_en = clamp_caption_fields(platform_captions.get("en", {}))
        caption_vi = clamp_caption_fields(platform_captions.get("vi", {}))

        post = create_scheduled_post(
            platform=platform,
            scheduled_at=body.scheduled_at,
            image_url=body.image_url,
            video_url=body.video_url,
            caption_en=caption_en,
            caption_vi=caption_vi,
            job_id=body.job_id,
        )
        created.append(_post_to_dict(post))

    return {"success": True, "count": len(created), "scheduled_posts": created}


@router.get("/schedule", tags=["Schedule"])
def list_schedules(status: Optional[str] = None):
    """
    Xem tất cả lịch đăng bài.
    Query param: ?status=pending | posted | failed | cancelled
    """
    posts = list_scheduled_posts(status=status)
    return {
        "total": len(posts),
        "scheduled_posts": [_post_to_dict(p) for p in posts],
    }


@router.get("/schedule/{post_id}", tags=["Schedule"])
def get_schedule(post_id: str):
    """Xem chi tiết 1 lịch đăng."""
    post = get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    return _post_to_dict(post)


@router.patch("/schedule/{post_id}", tags=["Schedule"])
def update_schedule_time(post_id: str, body: RescheduleRequest):
    """Đổi giờ đăng của 1 lịch đang ở trạng thái pending."""
    post = reschedule_post(post_id, body.scheduled_at)
    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found or already posted/cancelled — cannot reschedule.",
        )
    return {"success": True, "scheduled_post": _post_to_dict(post)}


@router.delete("/schedule/{post_id}", tags=["Schedule"])
def cancel_schedule(post_id: str):
    """Huỷ 1 lịch đăng đang chờ."""
    ok = cancel_scheduled_post(post_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Post not found or already posted/cancelled.",
        )
    return {"success": True, "message": "Scheduled post cancelled."}
