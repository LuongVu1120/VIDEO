"""
Multi-Format Exporter.

Từ 1 video/ảnh 9:16 gốc, tự động tạo thêm:
  1:1  (1080×1080) — Instagram Feed / Facebook square
  16:9 (1920×1080) — YouTube / Facebook landscape cover

Dùng FFmpeg. Không cần API key.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Literal

OUTPUT_ROOT = Path(__file__).parent.parent.parent.parent / "output" / "exports"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

FormatType = Literal["9:16", "1:1", "16:9"]


def _ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def _is_video(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}


# ---------------------------------------------------------------------------
# Core per-format converters
# ---------------------------------------------------------------------------

def _to_square(src: str, dst: str) -> str:
    """
    1:1  1080×1080 — crop center from 9:16 source.
    Video: trims top/bottom. Image: crops center square.
    """
    vf = (
        "scale=1080:1080:force_original_aspect_ratio=increase,"
        "crop=1080:1080"
    )
    if _is_video(src):
        cmd = ["ffmpeg", "-y", "-i", src,
               "-vf", vf, "-c:v", "libx264", "-preset", "fast",
               "-c:a", "copy", "-pix_fmt", "yuv420p", dst]
    else:
        cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf, dst]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return dst


def _to_landscape(src: str, dst: str) -> str:
    """
    16:9  1920×1080 — fit 9:16 inside 16:9 with blurred background.
    Left/right blurred fill gives a professional look (no black bars).
    """
    if _is_video(src):
        # Blurred background trick: scale main to height=1080,
        # blur-scale to 1920×1080 as bg, then overlay center.
        vf = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,boxblur=20:5[bg];"
            "[0:v]scale=-2:1080[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
        cmd = ["ffmpeg", "-y", "-i", src,
               "-filter_complex", vf, "-map", "[v]",
               "-c:v", "libx264", "-preset", "fast",
               "-map", "0:a?", "-c:a", "copy",
               "-pix_fmt", "yuv420p", dst]
    else:
        vf = (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,boxblur=20:5[bg];"
            "[0:v]scale=-2:1080[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
        cmd = ["ffmpeg", "-y", "-i", src,
               "-filter_complex", vf, "-map", "[v]", dst]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return dst


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_all_formats(
    source_path: str,
    job_id: str,
    formats: list[FormatType] = None,
) -> dict[str, str]:
    """
    Export source (9:16) into multiple formats.

    Args:
        source_path : local path to 9:16 video or image
        job_id      : used for output subfolder name
        formats     : list of ["9:16","1:1","16:9"]; default = all three

    Returns:
        dict mapping format → local output path
        e.g. {"9:16": "output/exports/abc/9_16.mp4",
               "1:1":  "output/exports/abc/1_1.mp4",
               "16:9": "output/exports/abc/16_9.mp4"}
    """
    if not _ffmpeg_ok():
        raise RuntimeError("FFmpeg not found. Install FFmpeg to use format export.")

    if formats is None:
        formats = ["9:16", "1:1", "16:9"]

    is_vid = _is_video(source_path)
    ext = Path(source_path).suffix if is_vid else ".jpg"

    out_dir = OUTPUT_ROOT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}

    for fmt in formats:
        safe_name = fmt.replace(":", "_")
        dst = str(out_dir / f"{safe_name}{ext}")

        if fmt == "9:16":
            # Source is already 9:16 — just copy
            shutil.copy2(source_path, dst)
            results[fmt] = dst

        elif fmt == "1:1":
            _to_square(source_path, dst)
            results[fmt] = dst

        elif fmt == "16:9":
            _to_landscape(source_path, dst)
            results[fmt] = dst

        print(f"  [Export] {fmt} → {dst}")

    return results


def get_format_urls(export_results: dict[str, str], base_url: str = "") -> dict[str, str]:
    """Convert local paths to public URLs served via /output/exports/..."""
    urls = {}
    for fmt, path in export_results.items():
        rel = path.replace("\\", "/").replace("output/", "", 1)
        urls[fmt] = f"{base_url}/output/{rel}"
    return urls
