"""
Content Calendar Scheduler Service.

Dùng APScheduler BackgroundScheduler để kiểm tra mỗi 60 giây xem có bài nào
đến giờ đăng chưa, nếu có thì gọi SocialPoster để đăng thật sự.

Lịch đăng được lưu trong bảng scheduled_posts (SQLite/PostgreSQL) —
persist qua các lần restart server.
"""

from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from ..core.config import settings
from ..models.scheduled_post import ScheduledPost
from .social_poster import SocialPoster


def _get_sync_db_url() -> str:
    import os
    db_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "arch_video.db"
    )
    if os.path.exists(db_path):
        return f"sqlite:///{os.path.abspath(db_path)}"
    url = settings.DATABASE_URL_SYNC or settings.DATABASE_URL
    return url.replace("+aiosqlite", "").replace("+asyncpg", "")


_engine = create_engine(_get_sync_db_url(), echo=False)
_SessionLocal = sessionmaker(bind=_engine)

_scheduler: Optional[BackgroundScheduler] = None


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler():
    """Start the background scheduler (call once on FastAPI startup)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _check_and_post_due,
        trigger=IntervalTrigger(seconds=60),
        id="content_calendar_check",
        replace_existing=True,
    )
    _scheduler.start()
    print("[Scheduler] Content calendar started — checking every 60 seconds.")


def stop_scheduler():
    """Gracefully stop the scheduler (call on FastAPI shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Content calendar stopped.")


# ---------------------------------------------------------------------------
# Core: check due posts and publish them
# ---------------------------------------------------------------------------

def _check_and_post_due():
    """Called every 60 s. Find all pending posts whose scheduled_at <= now and post them."""
    now = datetime.now(timezone.utc)
    db: Session = _SessionLocal()
    try:
        due = (
            db.query(ScheduledPost)
            .filter(
                ScheduledPost.status == "pending",
                ScheduledPost.scheduled_at <= now,
            )
            .all()
        )
        if not due:
            return

        print(f"[Scheduler] {len(due)} post(s) due — publishing now...")
        poster = SocialPoster()

        for post in due:
            try:
                # caption_en is what gets posted; caption_vi is UI-only
                result = poster.post_to_platform(
                    image_url=post.image_url or "",
                    video_url=post.video_url,
                    caption_data={"en": post.caption_en, "vi": post.caption_vi},
                    platform=post.platform,
                    dry_run=False,
                )
                post.status = "posted" if result.get("status") == "posted" else "failed"
                post.post_result = result
                post.posted_at = datetime.now(timezone.utc)
                if result.get("status") != "posted":
                    post.error_message = result.get("error", "Unknown error")
                print(f"  [{post.platform}] {post.status}: {result.get('post_url', '')}")
            except Exception as e:
                post.status = "failed"
                post.error_message = str(e)
                print(f"  [{post.platform}] ERROR: {e}")

        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CRUD helpers (called from API routes)
# ---------------------------------------------------------------------------

def create_scheduled_post(
    platform: str,
    scheduled_at: datetime,
    image_url: str,
    caption_en: dict,
    caption_vi: dict = None,
    video_url: str = None,
    job_id: str = None,
    user_id: str = None,
) -> ScheduledPost:
    """Insert a new scheduled post. Returns the saved ORM object."""
    db: Session = _SessionLocal()
    try:
        # Normalise to UTC
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        else:
            scheduled_at = scheduled_at.astimezone(timezone.utc)

        post = ScheduledPost(
            platform=platform,
            scheduled_at=scheduled_at,
            image_url=image_url,
            video_url=video_url,
            caption_en=caption_en or {},
            caption_vi=caption_vi or {},
            job_id=job_id,
            user_id=user_id,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post
    finally:
        db.close()


def list_scheduled_posts(user_id: str = None, status: str = None) -> list[ScheduledPost]:
    db: Session = _SessionLocal()
    try:
        q = db.query(ScheduledPost)
        if user_id:
            q = q.filter(ScheduledPost.user_id == user_id)
        if status:
            q = q.filter(ScheduledPost.status == status)
        return q.order_by(ScheduledPost.scheduled_at.asc()).all()
    finally:
        db.close()


def get_scheduled_post(post_id: str) -> Optional[ScheduledPost]:
    db: Session = _SessionLocal()
    try:
        return db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
    finally:
        db.close()


def cancel_scheduled_post(post_id: str) -> bool:
    """Cancel a pending post. Returns True if cancelled, False if not found/already done."""
    db: Session = _SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != "pending":
            return False
        post.status = "cancelled"
        db.commit()
        return True
    finally:
        db.close()


def reschedule_post(post_id: str, new_scheduled_at: datetime) -> Optional[ScheduledPost]:
    """Update the scheduled time of a pending post."""
    db: Session = _SessionLocal()
    try:
        post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id).first()
        if not post or post.status != "pending":
            return None
        if new_scheduled_at.tzinfo is None:
            new_scheduled_at = new_scheduled_at.replace(tzinfo=timezone.utc)
        post.scheduled_at = new_scheduled_at.astimezone(timezone.utc)
        db.commit()
        db.refresh(post)
        return post
    finally:
        db.close()
