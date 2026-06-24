"""Shared caption length limits for generation and social posting."""

# "Dưới 20 từ" — tối đa 19 từ (strictly fewer than 20)
MAX_POST_CAPTION_WORDS = 19

# Hashtag cho MXH (Instagram cho phép ~30; mục tiêu 10–15)
CAPTION_MIN_HASHTAGS = 10
CAPTION_MAX_HASHTAGS = 15


def count_words(text: str) -> int:
    if not text or not str(text).strip():
        return 0
    return len(str(text).strip().split())


def limit_caption_words(text: str, max_words: int = MAX_POST_CAPTION_WORDS) -> str:
    """Truncate text to at most max_words words."""
    if not text:
        return ""
    words = str(text).strip().split()
    if len(words) <= max_words:
        return str(text).strip()
    return " ".join(words[:max_words])


def normalize_hashtags(tags: list, max_count: int = CAPTION_MAX_HASHTAGS) -> list[str]:
    """Chuẩn hóa #prefix và giới hạn số lượng."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        t = str(raw).strip()
        if not t:
            continue
        if not t.startswith("#"):
            t = f"#{t.lstrip('#')}"
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= max_count:
            break
    return out


def clamp_caption_fields(data: dict, max_words: int = MAX_POST_CAPTION_WORDS) -> dict:
    """Apply word limit to caption body and call_to_action in a caption dict."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    if "caption" in out and out["caption"]:
        out["caption"] = limit_caption_words(out["caption"], max_words)
    if "call_to_action" in out and out["call_to_action"]:
        out["call_to_action"] = limit_caption_words(out["call_to_action"], max_words)
    if "hashtags" in out and out["hashtags"] is not None:
        out["hashtags"] = normalize_hashtags(out["hashtags"])
    return out
