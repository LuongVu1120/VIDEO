import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=True)

    platform: Mapped[str] = mapped_column(String(20))   # instagram|facebook|tiktok|youtube
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | posted | failed | cancelled

    # When to post (stored in UTC)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Media
    image_url: Mapped[str] = mapped_column(Text, nullable=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=True)

    # Captions — en is what gets posted, vi is shown in UI for user reference
    caption_en: Mapped[dict] = mapped_column(JSON, default=dict)
    caption_vi: Mapped[dict] = mapped_column(JSON, default=dict)

    # Result after posting
    post_result: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
