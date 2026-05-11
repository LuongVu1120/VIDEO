"""
Analytics & Best Posting Time API.

GET /api/v1/analytics/summary          — Tổng kết toàn bộ lịch đăng
GET /api/v1/analytics/post/{post_id}   — Metrics của 1 bài đăng cụ thể
GET /api/v1/analytics/best-times       — Gợi ý giờ đăng tốt nhất
GET /api/v1/analytics/best-times/{platform} — Gợi ý cho 1 platform
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ...services.analytics_service import (
    fetch_metrics_for_post,
    get_performance_summary,
    fetch_instagram_metrics,
    fetch_facebook_metrics,
)
from ...services.posting_time_advisor import (
    get_next_best_times,
    get_all_platforms_advice,
)
from ...services.scheduler_service import (
    list_scheduled_posts,
    get_scheduled_post,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/summary", tags=["Analytics"])
def analytics_summary(status: Optional[str] = None):
    """
    Tổng kết hiệu suất đăng bài:
    - Tổng số bài lên lịch, đã đăng, thất bại, đang chờ
    - Tỉ lệ thành công
    - Phân chia theo platform
    """
    posts = list_scheduled_posts(status=status)
    return get_performance_summary(posts)


@router.get("/analytics/post/{post_id}", tags=["Analytics"])
def analytics_single_post(post_id: str):
    """
    Kéo metrics thực tế từ Instagram/Facebook cho 1 bài đã đăng.
    Yêu cầu: bài phải ở trạng thái 'posted' và có post_result.
    """
    post = get_scheduled_post(post_id)
    if not post:
        raise HTTPException(404, detail="Scheduled post not found")
    if post.status != "posted":
        raise HTTPException(400, detail=f"Post status is '{post.status}', not 'posted'")

    metrics = fetch_metrics_for_post(post)
    if metrics is None:
        raise HTTPException(422, detail="Cannot fetch metrics: missing post_result or unsupported platform")

    return metrics


@router.get("/analytics/instagram/{media_id}", tags=["Analytics"])
def analytics_instagram(media_id: str):
    """Kéo metrics trực tiếp cho 1 Instagram media ID."""
    return fetch_instagram_metrics(media_id)


@router.get("/analytics/facebook/{post_id}", tags=["Analytics"])
def analytics_facebook(post_id: str):
    """Kéo metrics trực tiếp cho 1 Facebook post ID."""
    return fetch_facebook_metrics(post_id)


# ---------------------------------------------------------------------------
# Best posting times
# ---------------------------------------------------------------------------

@router.get("/analytics/best-times", tags=["Analytics"])
def best_times_all(n: int = Query(3, ge=1, le=5)):
    """
    Gợi ý {n} khung giờ đăng tốt nhất cho TẤT CẢ platform.
    Múi giờ: Asia/Ho_Chi_Minh (UTC+7).
    """
    return get_all_platforms_advice(n=n)


@router.get("/analytics/best-times/{platform}", tags=["Analytics"])
def best_times_platform(
    platform: str,
    n: int = Query(3, ge=1, le=5),
):
    """
    Gợi ý {n} khung giờ đăng tốt nhất cho 1 platform cụ thể.
    Platform: instagram | tiktok | facebook | youtube
    """
    valid = {"instagram", "tiktok", "facebook", "youtube"}
    if platform not in valid:
        raise HTTPException(400, detail=f"Platform phải là một trong: {', '.join(valid)}")

    from ...services.posting_time_advisor import PLATFORM_NOTES
    return {
        "platform": platform,
        "best_times": get_next_best_times(platform, n=n),
        "note": PLATFORM_NOTES.get(platform, ""),
    }
