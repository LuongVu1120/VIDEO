"""Ghép nhạc nền (BGM) vào video bằng FFmpeg — dùng thư viện local backend/bgm/."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

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

# Gợi ý mood BGM từ từ khóa phong cách / ánh sáng / bối cảnh
STYLE_MOOD_HINTS: dict[str, str] = {
    "minimalist": "serene",
    "minimal": "serene",
    "modern": "futuristic",
    "contemporary": "futuristic",
    "industrial": "dramatic",
    "brutalist": "dramatic",
    "brutal": "dramatic",
    "luxury": "luxurious",
    "luxurious": "luxurious",
    "elegant": "luxurious",
    "neoclassical": "luxurious",
    "classical": "luxurious",
    "mediterranean": "cozy",
    "rustic": "cozy",
    "farmhouse": "cozy",
    "tropical": "peaceful",
    "coastal": "peaceful",
    "scandinavian": "serene",
    "zen": "serene",
    "japanese": "serene",
    "organic": "peaceful",
    "nature": "peaceful",
    "garden": "peaceful",
    "urban": "futuristic",
    "tech": "futuristic",
    "smart": "futuristic",
    "dramatic": "dramatic",
    "cinematic": "dramatic",
    "epic": "dramatic",
    "cozy": "cozy",
    "warm": "cozy",
    "homely": "cozy",
    "peaceful": "peaceful",
    "calm": "peaceful",
    "serene": "serene",
    "tranquil": "serene",
}

# Demo track definitions (FFmpeg lavfi) — royalty-free ambient per mood
_DEMO_TRACK_SPECS: dict[str, list[tuple[str, str]]] = {
    "peaceful": [
        ("gentle_pink_ambient.mp3", "anoisesrc=d=50:c=pink:r=44100:a=0.012"),
        ("soft_waves.mp3", "anoisesrc=d=50:c=pink:r=44100:a=0.018"),
    ],
    "luxurious": [
        ("elegant_chord.mp3", "sine=frequency=261.63:duration=50"),
        ("premium_strings.mp3", "sine=frequency=329.63:duration=50"),
    ],
    "dramatic": [
        ("cinematic_brown.mp3", "anoisesrc=d=50:c=brown:r=44100:a=0.035"),
        ("epic_rumble.mp3", "sine=frequency=55:duration=50"),
    ],
    "cozy": [
        ("warm_acoustic.mp3", "sine=frequency=196:duration=50"),
        ("soft_folk.mp3", "sine=frequency=246.94:duration=50"),
    ],
    "futuristic": [
        ("synth_pulse.mp3", "sine=frequency=440:duration=50"),
        ("digital_ambient.mp3", "sine=frequency=523.25:duration=50"),
    ],
    "serene": [
        ("zen_quiet.mp3", "anoisesrc=d=50:c=pink:r=44100:a=0.006"),
        ("minimal_piano.mp3", "sine=frequency=293.66:duration=50"),
    ],
}


def _resolve_ffmpeg_paths() -> tuple[str | None, str | None]:
    """System ffmpeg/ffprobe, hoặc binary nhúng từ imageio-ffmpeg."""
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if ff:
        return ff, fp or ff
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled, bundled
    except Exception:
        pass
    return None, None


def _ffmpeg_available() -> bool:
    ff, _ = _resolve_ffmpeg_paths()
    return ff is not None


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


def infer_bgm_mood(style_analysis: dict[str, Any]) -> str:
    """
    Suy luận mood nhạc nền từ phân tích phong cách video (style, mood, lighting, environment).
  """
    scores: dict[str, int] = {m: 0 for m in MOOD_FOLDERS}

    raw_mood = str(style_analysis.get("mood", ""))
    scores[_normalize_mood(raw_mood)] += 4

    parts = [
        str(style_analysis.get("style", "")),
        str(style_analysis.get("lighting", "")),
        str(style_analysis.get("environment", "")),
        str(style_analysis.get("variation_name", "")),
        " ".join(style_analysis.get("materials", []) or []),
        " ".join(style_analysis.get("colors", []) or []),
        " ".join(style_analysis.get("key_features", []) or []),
    ]
    combined = " ".join(parts).lower()

    for hint, target in STYLE_MOOD_HINTS.items():
        if hint in combined:
            scores[target] += 2

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "peaceful"
    return best


def list_tracks_for_mood(mood: str) -> list[Path]:
    """Liệt kê tất cả track trong thư mục mood (bỏ file fallback ẩn nếu có track thật)."""
    root = _bgm_root()
    mood_dir = root / _normalize_mood(mood)
    tracks: list[Path] = []

    if mood_dir.is_dir():
        for ext in _audio_extensions():
            for path in sorted(mood_dir.glob(f"*{ext}")):
                if path.is_file() and path.stat().st_size > 1000:
                    if path.name.startswith("_"):
                        continue
                    tracks.append(path)

    if tracks:
        return tracks

    fallback = root / "peaceful" / "_fallback_ambient.mp3"
    if fallback.is_file():
        return [fallback]
    return []


def pick_bgm_track(
    mood: str,
    variation_index: int = 0,
    exclude_paths: set[str] | None = None,
) -> Optional[Path]:
    """
    Chọn track phù hợp mood; xoay vòng theo variation_index.
    Tránh trùng track trong cùng job (exclude_paths).
    """
    exclude = exclude_paths or set()
    tracks = list_tracks_for_mood(mood)

    if not tracks:
        for alt in MOOD_FOLDERS:
            if alt == _normalize_mood(mood):
                continue
            tracks = list_tracks_for_mood(alt)
            if tracks:
                break

    available = [t for t in tracks if str(t.resolve()) not in exclude]
    if not available:
        available = tracks

    if not available:
        return None

    idx = variation_index % len(available)
    return available[idx]


def _generate_demo_track(out_path: Path, lavfi_spec: str) -> bool:
    """Tạo 1 file ambient demo bằng FFmpeg."""
    ff, _ = _resolve_ffmpeg_paths()
    if not ff:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ff, "-y",
        "-f", "lavfi", "-i", lavfi_spec,
        "-ac", "2", "-q:a", "6", str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        return out_path.is_file() and out_path.stat().st_size > 1000
    except Exception as e:
        print(f"[BGM] Demo track failed ({out_path.name}): {e}")
        return False


def ensure_mood_library() -> int:
    """
    Tạo thư viện nhạc demo cho mỗi mood nếu thư mục trống.
    Trả về số file đã tạo.
    """
    if not _ffmpeg_available():
        return 0

    root = _bgm_root()
    created = 0

    for mood, specs in _DEMO_TRACK_SPECS.items():
        mood_dir = root / mood
        mood_dir.mkdir(parents=True, exist_ok=True)
        existing = list_tracks_for_mood(mood)
        if existing:
            continue
        for filename, lavfi in specs:
            out = mood_dir / filename
            if out.is_file():
                continue
            if _generate_demo_track(out, lavfi):
                created += 1
                print(f"[BGM] Created demo track: {out}")

    return created


def ensure_fallback_bgm() -> Optional[Path]:
    """Tạo file ambient rất nhẹ nếu chưa có nhạc trong thư viện (demo/dev)."""
    ensure_mood_library()
    track = pick_bgm_track("peaceful", 0)
    if track:
        return track

    root = _bgm_root()
    out = root / "peaceful" / "_fallback_ambient.mp3"
    if out.is_file():
        return out
    if _generate_demo_track(out, "anoisesrc=d=30:c=pink:r=44100:a=0.008"):
        return out
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
    ff, fp = _resolve_ffmpeg_paths()
    if not fp:
        return 5.0
    try:
        probe = json.loads(
            subprocess.run(
                [fp, "-v", "quiet", "-print_format", "json", "-show_format", media_path],
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
        )
        return float(probe["format"]["duration"])
    except Exception:
        pass
    # Fallback: parse ffmpeg -i stderr (bundled binary may lack ffprobe JSON)
    if ff:
        try:
            proc = subprocess.run(
                [ff, "-i", media_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
            if m:
                h, mi, s = m.groups()
                return int(h) * 3600 + int(mi) * 60 + float(s)
        except Exception:
            pass
    return 5.0


def _video_has_audio(video_path: str) -> bool:
    ff, fp = _resolve_ffmpeg_paths()
    if fp:
        try:
            probe = json.loads(
                subprocess.run(
                    [fp, "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                ).stdout
            )
            return any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        except Exception:
            pass
    if ff:
        try:
            proc = subprocess.run(
                [ff, "-i", video_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return "Audio:" in proc.stderr
        except Exception:
            pass
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
    ff, _ = _resolve_ffmpeg_paths()
    if not ff:
        raise RuntimeError("FFmpeg not available")

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
        ff, "-y",
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
    style_analysis: dict[str, Any] | None = None,
    variation_index: int = 0,
    used_tracks: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Ghép nhạc nền phù hợp phong cách video.
    Trả về dict metadata hoặc None nếu bỏ qua.
    """
    if not video_url or not settings.VIDEO_ADD_BGM:
        return None

    if not _ffmpeg_available():
        print("[BGM] FFmpeg not found — skip background music")
        return None

    ensure_mood_library()

    analysis = style_analysis or {"mood": mood}
    inferred_mood = infer_bgm_mood(analysis)
    exclude = set(used_tracks or [])
    track = pick_bgm_track(inferred_mood, variation_index, exclude) or ensure_fallback_bgm()

    if not track:
        print(
            f"[BGM] No music in {_bgm_root()}. "
            "Add .mp3 files under bgm/peaceful/ etc. See backend/bgm/README.md"
        )
        return None

    local_video, cleanup = _resolve_video_local(video_url)
    job_dir = OUTPUT_ROOT / job_id.replace("/", "_")
    job_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(job_dir / "video_with_bgm.mp4")

    try:
        mux_bgm_into_video(local_video, str(track), out_path)
        url = path_to_output_url(out_path)
        style_label = str(analysis.get("style", ""))
        variation_name = str(analysis.get("variation_name", ""))
        print(
            f"[BGM] Applied {track.name} "
            f"(mood={inferred_mood}, style={style_label}, variation={variation_name}) -> {url}"
        )
        return {
            "video_url": url,
            "bgm_track": track.name,
            "bgm_mood": inferred_mood,
            "bgm_path": str(track.resolve()),
            "style": style_label,
            "variation_name": variation_name,
        }
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
