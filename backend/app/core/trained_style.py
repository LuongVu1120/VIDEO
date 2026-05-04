"""
Trained Style Profile: Luu tru va quan ly Style Guide da hoc tu TRAIN AI dataset.
File nay duoc tao boi scripts/train_analyzer.py va duoc load boi vision_analyzer & prompt_writer.
"""

import json
import os
import sys
from pathlib import Path


_STYLE_GUIDE_CACHE = None
_SYSTEM_PROMPT_CACHE = None


# Fix Unicode cho Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


TRAINED_STYLE_FILE = Path(__file__).parent.parent.parent / "scripts" / "training_output" / "trained_style_profile.json"
TRAINED_PROMPT_FILE = Path(__file__).parent.parent.parent / "scripts" / "training_output" / "trained_system_prompt.txt"


def _print(msg: str):
    """Safe print that handles Unicode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Strip non-ASCII chars for Windows console
        print(msg.encode('ascii', errors='replace').decode('ascii'))


def load_style_guide() -> dict | None:
    """Load Style Guide tu file training_output."""
    global _STYLE_GUIDE_CACHE
    if _STYLE_GUIDE_CACHE is not None:
        return _STYLE_GUIDE_CACHE

    if not TRAINED_STYLE_FILE.exists():
        _print(f"[WARN] Khong tim thay Style Guide: {TRAINED_STYLE_FILE}")
        _print("[WARN] Hay chay: python backend/scripts/train_analyzer.py")
        return None

    try:
        with open(TRAINED_STYLE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        style_guide = data.get("style_guide", {})
        _STYLE_GUIDE_CACHE = style_guide
        count = style_guide.get('total_images_analyzed', 0)
        _print(f"[INFO] Load Style Guide: {count} images trained")
        return style_guide
    except Exception as e:
        _print(f"[ERROR] Load Style Guide failed: {e}")
        return None


def load_system_prompt() -> str | None:
    """Load System Prompt da duoc training."""
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is not None:
        return _SYSTEM_PROMPT_CACHE

    if not TRAINED_PROMPT_FILE.exists():
        _print(f"[WARN] Khong tim thay System Prompt: {TRAINED_PROMPT_FILE}")
        return None

    try:
        with open(TRAINED_PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt = f.read()
        _SYSTEM_PROMPT_CACHE = prompt
        _print(f"[INFO] Load System Prompt ({len(prompt)} chars)")
        return prompt
    except Exception as e:
        _print(f"[ERROR] Load System Prompt failed: {e}")
        return None


def get_trained_style_summary() -> str:
    """Tao summary ngan gon ve style da hoc de nhung vao prompt."""
    style_guide = load_style_guide()
    if not style_guide:
        return ""

    styles = [s for s, _ in style_guide.get("style_distribution", [])[:3]]
    materials = style_guide.get("top_materials", [])
    colors = style_guide.get("primary_palette", [])
    lighting = style_guide.get("dominant_lighting", "")
    mood = style_guide.get("dominant_mood", "")
    features = style_guide.get("top_key_features", [])
    env = [e for e, _ in style_guide.get("environments", [])[:2]]

    summary = f"""
## User's Trained Style Profile
- Preferred styles: {', '.join(styles)}
- Typical materials: {', '.join(materials)}
- Color palette: {', '.join(colors)}
- Default lighting: {lighting}
- Target mood: {mood}
- Key features: {', '.join(features)}
- Typical environments: {', '.join(env)}
"""
    return summary.strip()


def clear_cache():
    """Xoa cache (dung khi reload)."""
    global _STYLE_GUIDE_CACHE, _SYSTEM_PROMPT_CACHE
    _STYLE_GUIDE_CACHE = None
    _SYSTEM_PROMPT_CACHE = None
