"""
Before/After Comparison Video Service.

Nhận 2 ảnh (trước/sau) → tạo video so sánh 9:16 viral cho TikTok/Reels/Shorts.

3 hiệu ứng:
  split    — Màn hình chia đôi trái/phải, 2 ảnh song song
  reveal   — Ảnh "sau" trượt dần phủ lên ảnh "trước" (wipe effect)
  slideshow — Ảnh trước 3s → fade → Ảnh sau 4s

Tất cả output: 1080x1920 (9:16 portrait), libx264, yuv420p.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

# 9:16 portrait — TikTok / Instagram Reels / YouTube Shorts
W, H = 1080, 1920

EffectType = Literal["split", "reveal", "slideshow"]

# Windows/Linux font fallback (same logic as watermark_service)
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _find_font() -> str:
    for f in _FONT_CANDIDATES:
        if os.path.exists(f):
            return f.replace("\\", "/")
    return ""


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _scale_pad(idx: int, w: int, h: int) -> str:
    """FFmpeg filter: scale image to fit WxH with black letterbox."""
    return (
        f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )


def create_comparison_video(
    before_path: str,
    after_path: str,
    output_path: str,
    effect: EffectType = "reveal",
    add_labels: bool = True,
    duration: int = 8,
) -> str:
    """
    Main entry point.

    Args:
        before_path : local path to "before" image
        after_path  : local path to "after" image
        output_path : where to save the output .mp4
        effect      : "split" | "reveal" | "slideshow"
        add_labels  : overlay BEFORE / AFTER text labels
        duration    : total video duration in seconds (used for split & reveal)

    Returns:
        output_path on success
    """
    if not _ffmpeg_available():
        raise RuntimeError("FFmpeg not found. Install FFmpeg to use Before/After feature.")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if effect == "split":
        return _split_screen(before_path, after_path, output_path, duration, add_labels)
    elif effect == "reveal":
        return _reveal_wipe(before_path, after_path, output_path, duration, add_labels)
    else:
        return _slideshow_fade(before_path, after_path, output_path, add_labels)


# ---------------------------------------------------------------------------
# Effect 1: Split screen — side by side
# ---------------------------------------------------------------------------

def _split_screen(
    before: str, after: str, output: str, duration: int, add_labels: bool
) -> str:
    half_w = W // 2   # 540

    # Scale each image to 540x1920
    left_filter  = _scale_pad(0, half_w, H) + "[left]"
    right_filter = _scale_pad(1, half_w, H) + "[right]"
    stack = "[left][right]hstack=inputs=2[stacked]"

    # Optional labels
    if add_labels:
        font = _find_font()
        font_arg = f":fontfile='{font}'" if font else ""
        fs = 52
        label_filter = (
            f"[stacked]"
            f"drawtext=text='BEFORE'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x=({half_w}-text_w)/2:y={H}-{fs*2},"
            f"drawtext=text='AFTER'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x={half_w}+({half_w}-text_w)/2:y={H}-{fs*2}"
            f"[v]"
        )
        fc = f"{left_filter};{right_filter};{stack};{label_filter}"
    else:
        stack = "[left][right]hstack=inputs=2[v]"
        fc = f"{left_filter};{right_filter};{stack}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", before,
        "-loop", "1", "-i", after,
        "-filter_complex", fc,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return output


# ---------------------------------------------------------------------------
# Effect 2: Reveal / wipe — "after" slides in from left over "before"
# ---------------------------------------------------------------------------

def _reveal_wipe(
    before: str, after: str, output: str, duration: int, add_labels: bool
) -> str:
    reveal_dur = max(2, duration - 2)   # e.g. duration=8 → wipe takes 6s

    bg_filter = _scale_pad(0, W, H) + "[bg]"
    fg_filter = _scale_pad(1, W, H) + "[fg]"

    # blend: left part shows "after" (fg/B), right shows "before" (bg/A)
    # At time T, wipe position = W * min(T / reveal_dur, 1)
    blend = (
        f"[bg][fg]blend=all_expr="
        f"'if(lt(X\\,W*min(T/{reveal_dur}\\,1)),B,A)'[blended]"
    )

    if add_labels:
        font = _find_font()
        font_arg = f":fontfile='{font}'" if font else ""
        fs = 48
        # "BEFORE" label fades out; "AFTER" label fades in — approximate with opacity
        label_filter = (
            f"[blended]"
            f"drawtext=text='AFTER'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x=40:y={H}-{fs*2}"
            f":enable='gte(t,{reveal_dur * 0.6})',"
            f"drawtext=text='BEFORE'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x=w-text_w-40:y={H}-{fs*2}"
            f":enable='lte(t,{reveal_dur * 0.4})'"
            f"[v]"
        )
        fc = f"{bg_filter};{fg_filter};{blend};{label_filter}"
    else:
        blend_out = blend.replace("[blended]", "[v]")
        fc = f"{bg_filter};{fg_filter};{blend_out}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", before,
        "-loop", "1", "-i", after,
        "-filter_complex", fc,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return output


# ---------------------------------------------------------------------------
# Effect 3: Slideshow with fade transition
# ---------------------------------------------------------------------------

def _slideshow_fade(
    before: str, after: str, output: str, add_labels: bool,
    hold: int = 3, transition_dur: float = 1.0,
) -> str:
    total = hold * 2 + transition_dur

    bg_filter = _scale_pad(0, W, H) + "[v0]"
    fg_filter = _scale_pad(1, W, H) + "[v1raw]"

    if add_labels:
        font = _find_font()
        font_arg = f":fontfile='{font}'" if font else ""
        fs = 52
        # Add label to each clip before xfade
        v0_label = (
            f"[v0]drawtext=text='BEFORE'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x=(w-text_w)/2:y={H}-{fs*2}[v0l]"
        )
        v1_label = (
            f"[v1raw]drawtext=text='AFTER'{font_arg}:fontcolor=white:fontsize={fs}"
            f":box=1:boxcolor=black@0.55:boxborderw=12"
            f":x=(w-text_w)/2:y={H}-{fs*2}[v1]"
        )
        xfade = f"[v0l][v1]xfade=transition=fade:duration={transition_dur}:offset={hold}[v]"
        fc = f"{bg_filter};{fg_filter};{v0_label};{v1_label};{xfade}"
    else:
        fg_alias = fg_filter.replace("[v1raw]", "[v1]")
        xfade = f"[v0][v1]xfade=transition=fade:duration={transition_dur}:offset={hold}[v]"
        fc = f"{bg_filter};{fg_alias};{xfade}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", before,
        "-loop", "1", "-i", after,
        "-filter_complex", fc,
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "fast",
        "-t", str(total),
        "-pix_fmt", "yuv420p",
        output,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return output


# ---------------------------------------------------------------------------
# Caption generator for before/after content
# ---------------------------------------------------------------------------

def generate_before_after_caption(effect: EffectType, platform: str = "instagram") -> dict:
    """
    Generate a quick before/after caption using DeepSeek.
    Returns {"en": {...}, "vi": {...}}.
    """
    from openai import OpenAI
    from ..core.config import settings

    client = OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    from .caption_utils import MAX_POST_CAPTION_WORDS, clamp_caption_fields

    platform_note = (
        f"caption under 20 words (max {MAX_POST_CAPTION_WORDS}), 10-15 hashtags, short hook"
    )

    effect_desc = {
        "split": "split-screen side-by-side comparison",
        "reveal": "dramatic wipe reveal",
        "slideshow": "before and after slideshow",
    }.get(effect, "comparison")

    resp = client.chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"Write a {platform} caption for an architectural before/after {effect_desc} video.\n"
                f"Requirements: {platform_note}\n"
                "The caption should highlight the dramatic transformation.\n"
                "Return JSON:\n"
                '{"en": {"title":"...","caption":"...","hashtags":["#..."],"call_to_action":"..."},'
                ' "vi": {"title":"...","caption":"...","hashtags":["#..."],"call_to_action":"..."}}'
                "\nen = English for posting. vi = Vietnamese translation for user reference."
            ),
        }],
    )
    import re, json
    raw = resp.choices[0].message.content
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return {
                "en": clamp_caption_fields(data.get("en") or {}),
                "vi": clamp_caption_fields(data.get("vi") or {}),
            }
        except Exception:
            pass
    return {
        "en": clamp_caption_fields({"title": "", "caption": raw, "hashtags": [], "call_to_action": ""}),
        "vi": clamp_caption_fields({"title": "", "caption": "", "hashtags": [], "call_to_action": ""}),
    }
