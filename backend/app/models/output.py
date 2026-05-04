import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.database import Base


class Output(Base):
    __tablename__ = "outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), unique=True, nullable=False)

    # Style analysis result (reference image)
    style_analysis: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Creative variations (4 variations generated from reference)
    variations: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Prompts per variation
    prompts: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Generated images (all variations)
    images: Mapped[dict] = mapped_column(JSON, default=list)

    # Generated videos (one per variation)
    videos: Mapped[dict] = mapped_column(JSON, default=list, nullable=True)
    video_url: Mapped[str] = mapped_column(String(1000), nullable=True)  # legacy

    # Captions per platform
    captions: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Music suggestions per platform
    music_suggestions: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Social post previews
    social_post_preview: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Cost tracking
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    job = relationship("Job", back_populates="output")
