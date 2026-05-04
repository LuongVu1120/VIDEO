import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="queued"
    )  # queued | processing | completed | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(50), nullable=True)
    steps_completed: Mapped[dict] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Input
    original_image_path: Mapped[str] = mapped_column(String(500), nullable=True)

    # Options
    num_images: Mapped[int] = mapped_column(Integer, default=4)
    generate_video: Mapped[bool] = mapped_column(Boolean, default=True)
    video_duration: Mapped[int] = mapped_column(Integer, default=10)
    platforms: Mapped[dict] = mapped_column(JSON, default=["instagram"])
    auto_post: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider: Mapped[str] = mapped_column(String(20), default="claude")

    # Timing
    estimated_time_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    estimated_remaining_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="jobs")
    output = relationship("Output", back_populates="job", uselist=False, cascade="all, delete-orphan")
