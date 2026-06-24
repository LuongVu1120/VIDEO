"""fal.ai Kling video cost estimates (USD) — see https://fal.ai/models pricing pages."""

from ..core.config import settings

# Per-second rates (audio off) for O3 / V3 standard image-to-video
_O3_RATE_NO_AUDIO = 0.084
_O3_RATE_AUDIO = 0.112

# Kling 2.5 Turbo: flat $0.21 for 5s, +$0.042 per extra second
_TURBO_BASE_5S = 0.21
_TURBO_EXTRA_PER_SEC = 0.042


def estimate_fal_video_usd(
    duration_seconds: int,
    video_count: int = 1,
    *,
    model: str | None = None,
    generate_audio: bool | None = None,
) -> float:
    """Estimate fal video generation cost for one or more clips."""
    if video_count <= 0:
        return 0.0

    model = model or settings.FAL_VIDEO_MODEL
    audio = settings.FAL_VIDEO_GENERATE_AUDIO if generate_audio is None else generate_audio
    duration = max(3, min(15, int(duration_seconds or 5)))

    if "v2.5-turbo" in model:
        if duration <= 5:
            unit = _TURBO_BASE_5S
        else:
            unit = _TURBO_BASE_5S + (duration - 5) * _TURBO_EXTRA_PER_SEC
    else:
        rate = _O3_RATE_AUDIO if audio else _O3_RATE_NO_AUDIO
        unit = rate * duration

    return round(unit * video_count, 3)


def clamp_duration_for_model(duration_seconds: int, model: str | None = None) -> int:
    """Return a duration valid for the configured fal endpoint."""
    model = model or settings.FAL_VIDEO_MODEL
    d = int(duration_seconds or 5)
    if "v2.5-turbo" in model:
        return 10 if d > 7 else 5
    return max(3, min(15, d))
