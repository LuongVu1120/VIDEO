"""
Trained Video Style Profile: Luu tru va quan ly Video Style Guide da hoc tu VIDEO dataset.
File nay duoc tao boi scripts/video_train_analyzer.py va duoc load boi prompt_writer & tasks.
"""

import json
import os
import sys
from pathlib import Path


_VIDEO_GUIDE_CACHE = None
_VIDEO_PROMPT_CACHE = None


# Fix Unicode cho Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


TRAINED_VIDEO_FILE = Path(__file__).parent.parent.parent / "scripts" / "video_training_output" / "trained_video_profile.json"
TRAINED_VIDEO_PROMPT_FILE = Path(__file__).parent.parent.parent / "scripts" / "video_training_output" / "trained_video_system_prompt.txt"


def _print(msg: str):
    """Safe print that handles Unicode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


def load_video_style_guide() -> dict | None:
    """Load Video Style Guide tu file video_training_output."""
    global _VIDEO_GUIDE_CACHE
    if _VIDEO_GUIDE_CACHE is not None:
        return _VIDEO_GUIDE_CACHE

    if not TRAINED_VIDEO_FILE.exists():
        _print(f"[WARN] Khong tim thay Video Style Guide: {TRAINED_VIDEO_FILE}")
        _print("[WARN] Hay chay: python backend/scripts/video_train_analyzer.py")
        return None

    try:
        with open(TRAINED_VIDEO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        guide = data.get("video_style_guide", {})
        _VIDEO_GUIDE_CACHE = guide
        count = guide.get('total_videos_analyzed', 0)
        _print(f"[INFO] Load Video Style Guide: {count} videos trained")
        return guide
    except Exception as e:
        _print(f"[ERROR] Load Video Style Guide failed: {e}")
        return None


def load_video_system_prompt() -> str | None:
    """Load Video System Prompt da duoc training."""
    global _VIDEO_PROMPT_CACHE
    if _VIDEO_PROMPT_CACHE is not None:
        return _VIDEO_PROMPT_CACHE

    if not TRAINED_VIDEO_PROMPT_FILE.exists():
        _print(f"[WARN] Khong tim thay Video System Prompt: {TRAINED_VIDEO_PROMPT_FILE}")
        return None

    try:
        with open(TRAINED_VIDEO_PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt = f.read()
        _VIDEO_PROMPT_CACHE = prompt
        _print(f"[INFO] Load Video System Prompt ({len(prompt)} chars)")
        return prompt
    except Exception as e:
        _print(f"[ERROR] Load Video System Prompt failed: {e}")
        return None


def get_trained_video_style_summary() -> str:
    """Tao summary ngan gon ve video style da hoc."""
    guide = load_video_style_guide()
    if not guide:
        return ""

    cam = guide.get("dominant_camera_movement", "slow push-in")
    speed = guide.get("dominant_speed", "slow")
    pacing = guide.get("dominant_pacing", "steady")
    trans = guide.get("dominant_transition", "cut")
    pers = guide.get("dominant_perspective", "eye-level")
    atmos = guide.get("dominant_atmosphere", "cinematic")
    styles = [s for s, _ in guide.get("style_distribution", [])[:3]]
    mood = [m for m, _ in guide.get("mood_distribution", [])[:2]]

    summary = f"""
## User's Trained Video Style Profile
- Camera movement: {cam} at {speed} speed
- Pacing: {pacing}
- Transitions: {trans}
- Perspective: {pers}
- Atmosphere: {atmos}
- Preferred architectural styles (from video): {', '.join(styles)}
- Target mood: {', '.join(mood)}
"""
    return summary.strip()


def clear_video_cache():
    """Xoa cache video (dung khi reload)."""
    global _VIDEO_GUIDE_CACHE, _VIDEO_PROMPT_CACHE
    _VIDEO_GUIDE_CACHE = None
    _VIDEO_PROMPT_CACHE = None
