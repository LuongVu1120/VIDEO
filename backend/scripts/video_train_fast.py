"""
VIDEO TRAIN FAST — Phan tich toan bo video trong folder VIDEO.
Su dung ffprobe de trich xuat metadata (duration, resolution, fps, codec).
KHONG can API key.

Chay: python backend/scripts/video_train_fast.py
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ======================== PATHS ========================
VIDEO_DIR = str(Path(__file__).parent.parent.parent / "VIDEO")
OUTPUT_DIR = Path(__file__).parent / "video_training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_FILE = OUTPUT_DIR / "trained_video_profile.json"
PROMPT_FILE = OUTPUT_DIR / "trained_video_system_prompt.txt"


def get_video_files(directory: str) -> list[str]:
    """Lay tat ca file video."""
    valid_exts = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}
    files = []
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts:
            files.append(os.path.join(directory, f))
    return sorted(files)


def probe_video(video_path: str) -> dict:
    """Extract video metadata using ffprobe."""
    try:
        # Duration
        dur_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        dur_result = subprocess.run(dur_cmd, capture_output=True, text=True, timeout=15)
        duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 10.0
    except Exception:
        duration = 10.0
    
    try:
        # Resolution
        res_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path
        ]
        res_result = subprocess.run(res_cmd, capture_output=True, text=True, timeout=15)
        resolution = res_result.stdout.strip()
    except Exception:
        resolution = "unknown"
    
    try:
        # FPS
        fps_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        fps_result = subprocess.run(fps_cmd, capture_output=True, text=True, timeout=15)
        fps_str = fps_result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = round(float(num) / float(den), 2)
        else:
            fps = float(fps_str) if fps_str else 24.0
    except Exception:
        fps = 24.0
    
    try:
        # Codec
        codec_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        codec_result = subprocess.run(codec_cmd, capture_output=True, text=True, timeout=15)
        codec = codec_result.stdout.strip()
    except Exception:
        codec = "unknown"
    
    # Classify camera movement based on duration (heuristic)
    if duration > 20:
        movement = "slow pan / orbit"
    elif duration > 12:
        movement = "slow push-in"
    else:
        movement = "gentle push-in"
    
    # Classify quality from resolution
    if "1920" in resolution or "1080" in resolution:
        quality = "Full HD"
    elif "3840" in resolution or "2160" in resolution:
        quality = "4K Ultra HD"
    elif "1280" in resolution or "720" in resolution:
        quality = "HD"
    else:
        quality = str(resolution)
    
    return {
        "file": os.path.basename(video_path),
        "duration": round(duration, 1),
        "resolution": resolution,
        "fps": fps,
        "codec": codec,
        "quality": quality,
        "camera_movement": movement,
        "movement_speed": "slow" if duration > 10 else "moderate",
        "pacing": "relaxed" if duration > 8 else "steady",
        "atmosphere": "cinematic",
        "perspective": "eye-level",
    }


def create_video_summary(results: list[dict]) -> dict:
    """Tao video style summary."""
    movements = Counter()
    speeds = Counter()
    pacings = Counter()
    qualities = Counter()
    codecs = Counter()
    
    for r in results:
        if not r:
            continue
        movements[r.get("camera_movement", "unknown")] += 1
        speeds[r.get("movement_speed", "slow")] += 1
        pacings[r.get("pacing", "relaxed")] += 1
        qualities[r.get("quality", "unknown")] += 1
        codecs[r.get("codec", "unknown")] += 1
    
    total = len([r for r in results if r])
    
    return {
        "total_videos_analyzed": total,
        "analysis_method": "ffprobe metadata extraction (no API)",
        "dominant_camera_movement": movements.most_common(1)[0][0] if movements else "slow push-in",
        "camera_movement_distribution": movements.most_common(5),
        "dominant_speed": speeds.most_common(1)[0][0] if speeds else "slow",
        "movement_speed_distribution": speeds.most_common(3),
        "dominant_pacing": pacings.most_common(1)[0][0] if pacings else "relaxed",
        "pacing_distribution": pacings.most_common(3),
        "dominant_atmosphere": "cinematic",
        "dominant_perspective": "eye-level",
        "video_quality_distribution": qualities.most_common(5),
        "detail": results,
    }


def generate_video_prompt(guide: dict) -> str:
    """Tao video system prompt."""
    cam = guide.get("dominant_camera_movement", "slow push-in")
    speed = guide.get("dominant_speed", "slow")
    pacing = guide.get("dominant_pacing", "relaxed")
    
    return f"""You are an expert architectural cinematographer and AI video director.
You have analyzed {guide.get('total_videos_analyzed', 0)} architectural reference videos.

## TRAINED VIDEO STYLE

### Camera Movement
Signature: {cam} at {speed} speed
Default pacing: {pacing}
Perspective: eye-level
Atmosphere: cinematic

## VIDEO PROMPT RULES

### Structure (100-150 words)
1. Camera movement: start with {cam}
2. Scene description: architecture, materials, lighting
3. Time of day and atmosphere: golden hour / blue hour / twilight
4. Speed: {speed}, pacing: {pacing}
5. Duration: 8-15 seconds
6. Quality: cinematic, 4k, smooth motion, professional, gimbal stabilized

### Negative Prompt
distorted, low quality, blurry, unnatural motion, jittery, choppy, warped perspective, cartoonish, CGI looking, artificial

### Output Format
JSON: {{"image_prompt", "video_prompt", "negative_prompt", "style_tags"}}
"""


def main():
    print("=" * 60)
    print("VIDEO TRAIN FAST — ffprobe Metadata Analysis")
    print("=" * 60)
    
    if not os.path.exists(VIDEO_DIR):
        print(f"[ERROR] Video folder not found: {VIDEO_DIR}")
        return
    
    videos = get_video_files(VIDEO_DIR)
    print(f"Found {len(videos)} videos\n")
    
    results = []
    for i, video_path in enumerate(videos):
        name = os.path.basename(video_path)[:55]
        result = probe_video(video_path)
        results.append(result)
        print(f"[{i+1}/{len(videos)}] {name}")
        print(f"         Duration: {result['duration']}s | "
              f"Resolution: {result['resolution']} | "
              f"FPS: {result['fps']} | "
              f"Codec: {result['codec']}")
    
    # Summarize
    print(f"\n=== Generating video style profile ===")
    guide = create_video_summary(results)
    
    profile = {"video_style_guide": guide}
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {PROFILE_FILE}")
    
    prompt = generate_video_prompt(guide)
    with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"[SAVE] {PROMPT_FILE}")
    
    print("\n" + "=" * 60)
    print("✅ VIDEO TRAINING COMPLETE!")
    print(f"   Videos: {guide['total_videos_analyzed']}")
    print(f"   Camera: {guide['dominant_camera_movement']}")
    print(f"   Speed: {guide['dominant_speed']}")
    print(f"   Pacing: {guide['dominant_pacing']}")
    print(f"   Qualities: {dict(guide['video_quality_distribution'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
