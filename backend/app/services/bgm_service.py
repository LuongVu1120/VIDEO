"""Ghép nhạc nền (BGM) vào video bằng FFmpeg — dùng thư viện local backend/bgm/."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

from ..core.config import settings

_BACKEND_DIR = Path(__file__).parent.parent.parent
OUTPUT_ROOT = _BACKEND_DIR / "output"
DEFAULT_BGM_ROOT = _BACKEND_DIR / "bgm"

MOOD_FOLDERS = (
    "peaceful",
    "luxurious",
    "dramatic",
    "cozy",
    "futuristic",
    "serene",
)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _bgm_root() -> Path:
    custom = (settings.BGM_LIBRARY_DIR or "").strip()
    if custom:
        return Path(custom)
    return DEFAULT_BGM_ROOT


def _normalize_mood(mood: str) -> str:
    m = (mood or "peaceful").lower().strip()
    if m in MOOD_FOLDERS:
        return m
    for key in MOOD_FOLDERS:
        if key in m:
            return key
    return "peaceful"


def _audio_extensions() -> tuple[str, ...]:
    return (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")


def pick_bgm_track(mood: str) -> Optional[Path]:
    """Chọn file nhạc đầu tiên trong thư mục mood, hoặc fallback."""
    root = _bgm_root()
    mood_dir = root / _normalize_mood(mood)
    for folder in (mood_dir, root):
        if not folder.is_dir():
            continue
        for ext in _audio_extensions():
            for path in sorted(folder.glob(f"*{ext}")):
                if path.is_file() and path.stat().st_size > 1000:
                    return path
    fallback = root / "peaceful" / "_fallback_ambient.mp3"
    if fallback.is_file():
        return fallback
    return None


def ensure_fallback_bgm() -> Optional[Path]:
    """Tạo file ambient rất nhẹ nếu chưa có nhạc trong thư viện (demo/dev)."""
    root = _bgm_root()
    root.mkdir(parents=True, exist_ok=True)
    out = root / "peaceful" / "_fallback_ambient.mp3"
    if out.is_file():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    if not _ffmpeg_available():
        return None
    # Ambient pink noise ~30s, volume thấp
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "anoisesrc=d=30:c=pink:r=44100:a=0.008",
        "-ac", "2", "-q:a", "6", str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        print(f"[BGM] Created fallback ambient track: {out}")
        return out if out.is_file() else None
    except Exception as e:
        print(f"[BGM] Could not create fallback track: {e}")
        return None


def path_to_output_url(local_path: str | Path) -> str:
    """Chuyển đường dẫn trong output/ sang URL /output/..."""
    output_root = OUTPUT_ROOT.resolve()
    p = Path(local_path).resolve()
    try:
        rel = p.relative_to(output_root)
        return "/output/" + rel.as_posix()
    except ValueError:
        return str(p).replace("\\", "/")


def _probe_duration(media_path: str) -> float:
    try:
        probe = json.loads(
            subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", media_path],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
        )
        return float(probe["format"]["duration"])
    except Exception:
        return 5.0


def _video_has_audio(video_path: str) -> bool:
    try:
        probe = json.loads(
            subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
        )
        return any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
    except Exception:
        return False


def _resolve_video_local(video_url: str) -> tuple[str, bool]:
    """
    Trả về (đường dẫn local, cần_xóa_sau_khi_dùng).
    Hỗ trợ URL http, /output/..., hoặc path tuyệt đối.
    """
    if video_url.startswith("http://") or video_url.startswith("https://"):
        resp = requests.get(video_url, timeout=120, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()
        return tmp.name, True

    if video_url.startswith("/output/"):
        rel = video_url[len("/output/"):].lstrip("/")
        local = OUTPUT_ROOT / rel
        if not local.is_file():
            raise FileNotFoundError(f"Video not found: {video_url} -> {local}")
        return str(local.resolve()), False

    p = Path(video_url)
    if p.is_file():
        return str(p.resolve()), False

    raise FileNotFoundError(f"Video not found: {video_url}")


def mux_bgm_into_video(
    video_path: str,
    bgm_path: str,
    output_path: str,
    volume: float | None = None,
) -> str:
    """Ghép BGM vào video (silent hoặc mix với audio có sẵn)."""
    vol = volume if volume is not None else settings.BGM_VOLUME
    vol = max(0.05, min(0.6, float(vol)))
    duration = _probe_duration(video_path)
    dur_str = f"{duration:.3f}"

    if _video_has_audio(video_path):
        filter_complex = (
            f"[1:a]volume={vol},atrim=0:{dur_str},asetpts=PTS-STARTPTS[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        maps = ["-map", "0:v", "-map", "[aout]"]
    else:
        filter_complex = (
            f"[1:a]volume={vol},atrim=0:{dur_str},asetpts=PTS-STARTPTS[aout]"
        )
        maps = ["-map", "0:v", "-map", "[aout]"]

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        *maps,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "ffmpeg BGM mux failed")
    return output_path


def apply_bgm_to_video(
    video_url: str | None,
    mood: str = "peaceful",
    job_id: str = "job",
) -> str | None:
    """
    Ghép nhạc nền vào video_url. Trả về URL /output/... hoặc None nếu bỏ qua.
    """
    if not video_url or not settings.VIDEO_ADD_BGM:
        return video_url

    if not _ffmpeg_available():
        print("[BGM] FFmpeg not found — skip background music")
        return video_url

    track = pick_bgm_track(mood) or ensure_fallback_bgm()
    if not track:
        print(
            f"[BGM] No music in {_bgm_root()}. "
            "Add .mp3 files under bgm/peaceful/ etc. See backend/bgm/README.md"
        )
        return video_url

    local_video, cleanup = _resolve_video_local(video_url)
    job_dir = OUTPUT_ROOT / job_id.replace("/", "_")
    job_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(job_dir / "video_with_bgm.mp4")

    try:
        mux_bgm_into_video(local_video, str(track), out_path)
        url = path_to_output_url(out_path)
        print(f"[BGM] Applied {track.name} (mood={_normalize_mood(mood)}) -> {url}")
        return url
    finally:
        if cleanup and os.path.exists(local_video):
            os.unlink(local_video)


def list_library_status() -> dict:
    """Trạng thái thư viện nhạc (cho health/debug)."""
    root = _bgm_root()
    counts = {}
    for mood in MOOD_FOLDERS:
        folder = root / mood
        counts[mood] = len(
            [p for p in folder.glob("*") if p.suffix.lower() in _audio_extensions()]
        ) if folder.is_dir() else 0
    return {"bgm_root": str(root), "tracks_by_mood": counts}
