"""
Best Posting Time Advisor.

Dựa trên nghiên cứu về engagement rate theo platform,
gợi ý 3 khung giờ đăng bài tốt nhất tiếp theo cho người dùng
(tính theo múi giờ Việt Nam UTC+7).
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # UTC+7

# Dữ liệu khung giờ vàng theo nghiên cứu engagement (giờ địa phương)
# weekday: 0=Monday ... 6=Sunday
BEST_SLOTS: dict[str, list[dict]] = {
    "instagram": [
        {"weekdays": [1, 2, 4],    "hours": [11, 14, 17, 20], "label": "Thứ Ba, Tư, Sáu — 11h, 14h, 17h, 20h"},
        {"weekdays": [5, 6],       "hours": [10, 19],          "label": "Cuối tuần — 10h, 19h"},
    ],
    "tiktok": [
        {"weekdays": [1, 3, 4],    "hours": [7, 12, 17, 21],  "label": "Thứ Ba, Năm, Sáu — 7h, 12h, 17h, 21h"},
        {"weekdays": [5, 6],       "hours": [9, 15, 21],       "label": "Cuối tuần — 9h, 15h, 21h"},
    ],
    "facebook": [
        {"weekdays": [2, 3, 4],    "hours": [9, 13, 16],      "label": "Thứ Tư, Năm, Sáu — 9h, 13h, 16h"},
        {"weekdays": [0, 5],       "hours": [10, 14],          "label": "Thứ Hai, Sáu — 10h, 14h"},
    ],
    "youtube": [
        {"weekdays": [4, 5, 6, 0], "hours": [14, 17, 20],     "label": "Thứ Sáu–Chủ Nhật, Thứ Hai — 14h, 17h, 20h"},
    ],
}

PLATFORM_NOTES = {
    "instagram": "Engagement cao nhất vào giờ nghỉ trưa và tối. Tránh đăng trước 9h.",
    "tiktok":    "Algorithm ưu tiên bài đăng sáng sớm 7h và tối 21h. Consistency quan trọng hơn timing.",
    "facebook":  "Người dùng active nhất giờ làm việc (9–17h). Tránh đăng cuối tuần.",
    "youtube":   "Đăng trước 17h để video index kịp prime time tối. Thứ 6–Chủ Nhật xem nhiều nhất.",
}


def get_next_best_times(
    platform: str,
    n: int = 3,
    from_dt: datetime = None,
) -> list[dict]:
    """
    Trả về n khung giờ đăng bài tốt nhất tiếp theo cho platform.

    Args:
        platform : instagram | tiktok | facebook | youtube
        n        : số lượng gợi ý (mặc định 3)
        from_dt  : tính từ thời điểm nào (mặc định = ngay bây giờ)

    Returns:
        list of dicts:
          {"datetime_vn": "2026-05-16T19:00:00+07:00",
           "datetime_utc": "2026-05-16T12:00:00Z",
           "day_label": "Thứ Sáu",
           "time_label": "19:00",
           "score": "⭐⭐⭐"}
    """
    slots = BEST_SLOTS.get(platform, BEST_SLOTS["instagram"])
    now = (from_dt or datetime.now(VN_TZ)).astimezone(VN_TZ)

    candidates: list[datetime] = []

    # Scan next 14 days for matching slots
    for day_offset in range(14):
        check = now + timedelta(days=day_offset)
        wd = check.weekday()
        for slot in slots:
            if wd in slot["weekdays"]:
                for hour in slot["hours"]:
                    candidate = check.replace(hour=hour, minute=0, second=0, microsecond=0)
                    if candidate > now + timedelta(minutes=30):
                        candidates.append(candidate)

    candidates.sort()
    results = []
    for dt in candidates[:n]:
        dt_utc = dt.astimezone(timezone.utc)
        day_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm",
                     "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        # Score: morning/evening = 3 stars, midday = 2 stars
        stars = "⭐⭐⭐" if dt.hour in (7, 17, 19, 20, 21) else "⭐⭐"
        results.append({
            "datetime_vn":  dt.isoformat(),
            "datetime_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "day_label":    day_names[dt.weekday()],
            "time_label":   dt.strftime("%H:%M"),
            "score":        stars,
            "iso_for_schedule": dt.isoformat(),  # dùng trực tiếp cho POST /schedule
        })

    return results


def get_all_platforms_advice(n: int = 3) -> dict:
    """Trả về gợi ý cho tất cả 4 platform cùng lúc."""
    platforms = ["instagram", "tiktok", "facebook", "youtube"]
    return {
        p: {
            "best_times": get_next_best_times(p, n),
            "note": PLATFORM_NOTES.get(p, ""),
        }
        for p in platforms
    }
