#!/usr/bin/env python3
"""Tạo thư viện nhạc nền demo cho mỗi mood (cần FFmpeg)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.bgm_service import ensure_mood_library, list_library_status


def main() -> int:
    created = ensure_mood_library()
    status = list_library_status()
    print(f"Created {created} demo track(s).")
    print("Library status:", status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
