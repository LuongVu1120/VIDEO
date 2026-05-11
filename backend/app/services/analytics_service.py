"""
Analytics Service — kéo metrics từ Instagram và Facebook sau khi đăng bài.

Metrics trả về:
  Instagram: likes, comments, reach, impressions, saved, shares (Reels)
  Facebook : likes, comments, shares, reach, impressions
"""

import requests
from datetime import datetime, timezone
from typing import Optional

from ..core.config import settings


# ---------------------------------------------------------------------------
# Instagram (Graph API)
# ---------------------------------------------------------------------------

def fetch_instagram_metrics(media_id: str, access_token: str = None) -> dict:
    """
    Kéo insights của 1 bài đăng Instagram.
    media_id: ID bài đăng (trả về khi post thành công).
    """
    token = access_token or settings.INSTAGRAM_ACCESS_TOKEN
    if not token:
        return {"error": "INSTAGRAM_ACCESS_TOKEN not configured"}

    # Basic counts (available on all media)
    basic_url = f"https://graph.facebook.com/v21.0/{media_id}"
    basic_params = {
        "fields": "like_count,comments_count,timestamp,media_type,permalink",
        "access_token": token,
    }
    try:
        basic = requests.get(basic_url, params=basic_params, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}

    # Insights (reach, impressions, saved — requires Business/Creator account)
    insight_url = f"https://graph.facebook.com/v21.0/{media_id}/insights"
    insight_metrics = "reach,impressions,saved"
    if basic.get("media_type") in ("VIDEO", "REELS"):
        insight_metrics += ",video_views,plays"

    insight_params = {
        "metric": insight_metrics,
        "access_token": token,
    }
    insights = {}
    try:
        resp = requests.get(insight_url, params=insight_params, timeout=15).json()
        for item in resp.get("data", []):
            insights[item["name"]] = item.get("values", [{}])[-1].get("value", 0)
    except Exception:
        pass  # Insights may not be available on personal accounts

    return {
        "platform": "instagram",
        "media_id": media_id,
        "permalink": basic.get("permalink", ""),
        "media_type": basic.get("media_type", ""),
        "posted_at": basic.get("timestamp", ""),
        "likes": basic.get("like_count", 0),
        "comments": basic.get("comments_count", 0),
        "reach": insights.get("reach", 0),
        "impressions": insights.get("impressions", 0),
        "saved": insights.get("saved", 0),
        "video_views": insights.get("video_views", 0),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Facebook (Graph API)
# ---------------------------------------------------------------------------

def fetch_facebook_metrics(post_id: str, access_token: str = None) -> dict:
    """
    Kéo insights của 1 bài đăng Facebook Page.
    post_id: dạng "{page_id}_{post_id}" hoặc ID bài đăng.
    """
    token = access_token or settings.FACEBOOK_PAGE_ACCESS_TOKEN
    if not token:
        return {"error": "FACEBOOK_PAGE_ACCESS_TOKEN not configured"}

    # Basic engagement
    basic_url = f"https://graph.facebook.com/v21.0/{post_id}"
    basic_params = {
        "fields": "message,created_time,permalink_url,"
                  "likes.summary(true),comments.summary(true),shares",
        "access_token": token,
    }
    try:
        basic = requests.get(basic_url, params=basic_params, timeout=15).json()
    except Exception as e:
        return {"error": str(e)}

    # Page post insights
    insights_url = f"https://graph.facebook.com/v21.0/{post_id}/insights"
    insights_params = {
        "metric": "post_impressions,post_reach,post_engaged_users,post_clicks",
        "access_token": token,
    }
    insights = {}
    try:
        resp = requests.get(insights_url, params=insights_params, timeout=15).json()
        for item in resp.get("data", []):
            insights[item["name"]] = item.get("values", [{}])[-1].get("value", 0)
    except Exception:
        pass

    return {
        "platform": "facebook",
        "post_id": post_id,
        "permalink": basic.get("permalink_url", ""),
        "posted_at": basic.get("created_time", ""),
        "likes": basic.get("likes", {}).get("summary", {}).get("total_count", 0),
        "comments": basic.get("comments", {}).get("summary", {}).get("total_count", 0),
        "shares": basic.get("shares", {}).get("count", 0),
        "impressions": insights.get("post_impressions", 0),
        "reach": insights.get("post_reach", 0),
        "engaged_users": insights.get("post_engaged_users", 0),
        "clicks": insights.get("post_clicks", 0),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Aggregate: fetch all metrics for a scheduled post
# ---------------------------------------------------------------------------

def fetch_metrics_for_post(scheduled_post) -> Optional[dict]:
    """
    Nhận 1 ScheduledPost ORM object, kéo metrics dựa vào platform và post_result.
    Returns None nếu không có đủ thông tin.
    """
    if not scheduled_post or scheduled_post.status != "posted":
        return None

    result = scheduled_post.post_result or {}
    platform = scheduled_post.platform

    if platform == "instagram":
        # Extract media ID from post_url: https://instagram.com/p/{media_id}
        post_url = result.get("post_url", "")
        media_id = post_url.rstrip("/").split("/")[-1] if post_url else ""
        if not media_id:
            return None
        return fetch_instagram_metrics(media_id)

    elif platform == "facebook":
        post_url = result.get("post_url", "")
        post_id = post_url.rstrip("/").split("/")[-1] if post_url else ""
        if not post_id:
            return None
        return fetch_facebook_metrics(post_id)

    return None


# ---------------------------------------------------------------------------
# Summary across all scheduled posts
# ---------------------------------------------------------------------------

def get_performance_summary(posts: list) -> dict:
    """
    Tính tổng kết performance từ list ScheduledPost objects.
    """
    total_posts = len(posts)
    posted = [p for p in posts if p.status == "posted"]
    failed = [p for p in posts if p.status == "failed"]
    pending = [p for p in posts if p.status == "pending"]

    platform_counts: dict[str, int] = {}
    for p in posted:
        platform_counts[p.platform] = platform_counts.get(p.platform, 0) + 1

    return {
        "total_scheduled": total_posts,
        "posted": len(posted),
        "failed": len(failed),
        "pending": len(pending),
        "success_rate": round(len(posted) / total_posts * 100, 1) if total_posts else 0,
        "by_platform": platform_counts,
    }
