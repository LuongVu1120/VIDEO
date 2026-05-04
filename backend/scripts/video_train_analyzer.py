"""
Video Train Analyzer: Phân tích toàn bộ video trong thư mục VIDEO để học style.

Khác với train_analyzer.py (học style ảnh tĩnh), script này học:
  - Camera movement & góc quay trong video
  - Tốc độ di chuyển camera (pacing)
  - Transition giữa các cảnh
  - Lighting thay đổi theo thời gian trong video
  - Composition động (khác với ảnh tĩnh)
  - Duration & nhịp điệu video

Sử dụng GPT-4o Vision để phân tích từng frame chính.
"""

import sys
import os
import json
import base64
import time
import subprocess
import tempfile
from pathlib import Path

# Them backend vao sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load .env file - thu project root truoc, fallback ve backend folder
from dotenv import load_dotenv
env_paths = [
    os.path.join(os.path.dirname(__file__), '..', '..', '.env'),  # project root
    os.path.join(os.path.dirname(__file__), '..', '.env'),        # backend folder
]
for ep in env_paths:
    if os.path.exists(ep):
        load_dotenv(ep)
        print(f"[DEBUG] Loaded .env from: {ep}")
        break

print(f"[DEBUG] OPENAI_API_KEY set: {'OPENAI_API_KEY' in os.environ and len(os.environ['OPENAI_API_KEY']) > 20}")
print(f"[DEBUG] DEEPSEEK_API_KEY set: {'DEEPSEEK_API_KEY' in os.environ and len(os.environ['DEEPSEEK_API_KEY']) > 10}")

from openai import OpenAI


# === CONFIGURATION ===

VIDEO_DIR = r"D:\TU_DONG_DANG_VIDEO\VIDEO"
OUTPUT_DIR = Path(__file__).parent / "video_training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# File luu ket qua
RESULT_FILE = OUTPUT_DIR / "video_analysis_results.json"
SUMMARY_FILE = OUTPUT_DIR / "video_style_summary.json"

# So frame can extract cho moi video (de gui len GPT-4o Vision)
FRAMES_PER_VIDEO = 5
# Threshold dung luong anh de gui len API (tranh timeout)
MAX_FRAME_SIZE_BYTES = 500 * 1024  # 500KB


def get_video_files(directory: str) -> list[str]:
    """Lay tat ca file video trong thu muc."""
    valid_exts = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}
    files = []
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts:
            files.append(os.path.join(directory, f))
    return sorted(files)


def extract_frames(video_path: str, num_frames: int = FRAMES_PER_VIDEO) -> list[dict]:
    """
    Trich xuat frame tu video bang ffmpeg.
    Tra ve list: [{"index": 0, "timestamp": 0.0, "base64": "..."}, ...]
    """
    frames = []

    # Lay duration video bang ffprobe
    try:
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=15)
        duration = float(result.stdout.strip())
    except Exception as e:
        print(f"  [WARN] Khong the lay duration: {e}, mac dinh 10s")
        duration = 10.0

    # Tinh toan 5 frame tai cac moc thoi gian
    timestamps = []
    for i in range(num_frames):
        ts = (duration / (num_frames + 1)) * (i + 1)
        timestamps.append(ts)

    for idx, ts in enumerate(timestamps):
        try:
            # Tao file tam
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            # Extract frame bang ffmpeg
            extract_cmd = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",  # quality 2 = cao
                tmp_path
            ]
            subprocess.run(extract_cmd, capture_output=True, timeout=30)

            # Doc frame, resize neu can
            with open(tmp_path, "rb") as f:
                img_data = f.read()

            # Neu qua lon, giam quality
            if len(img_data) > MAX_FRAME_SIZE_BYTES:
                # Resize bang ffmpeg
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp2:
                    tmp2_path = tmp2.name
                resize_cmd = [
                    "ffmpeg", "-y",
                    "-i", tmp_path,
                    "-vf", "scale=1024:-1",
                    "-q:v", "5",
                    tmp2_path
                ]
                subprocess.run(resize_cmd, capture_output=True, timeout=15)
                with open(tmp2_path, "rb") as f:
                    img_data = f.read()
                os.unlink(tmp2_path)

            base64_data = base64.b64encode(img_data).decode("utf-8")
            frames.append({
                "index": idx,
                "timestamp": round(ts, 1),
                "size_bytes": len(img_data),
                "base64": base64_data,
            })

            os.unlink(tmp_path)

        except Exception as e:
            print(f"  [WARN] Frame {idx} tai {ts}s: {e}")

    return frames


def analyze_video_frames(frames_base64: list[str], video_name: str) -> dict:
    """
    Phan tich cac frame cua video bang GPT-4o Vision.
    Gui nhieu frame cung luc de AI thay duoc su thay doi theo thoi gian.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment or .env file")

    client = OpenAI(api_key=api_key)

    # Gioi han so frame gui len (API gioi han)
    max_frames = min(len(frames_base64), 5)

    # Xay dung prompt
    prompt = f"""You are analyzing frames extracted from an architectural video "{video_name}".

These {max_frames} frames are sampled at regular intervals throughout the video.
Analyze BOTH the architectural content AND the videography style.

## ARCHITECTURE ANALYSIS (for each visible building)
- style: architectural style (Contemporary / Modern Minimalist / Neoclassical / etc.)
- materials: visible materials
- colors: color palette
- lighting: lighting conditions
- mood: emotional tone
- architecture_type: house / villa / mansion / etc.
- environment: surrounding context

## VIDEOGRAPHY ANALYSIS
- camera_movement: describe the dominant camera movement throughout the video
  (Options: slow push-in / gentle pull-out / dolly forward / dolly backward / 
   crane up / crane down / pan left / pan right / orbit / static / 
   tracking shot / handheld / glidecam / aerial drone / combination)

- movement_speed: speed of camera movement
  (very slow / slow / moderate / fast)

- pacing: overall rhythm of the video
  (relaxed / steady / dynamic / dramatic)

- transitions: how scenes or viewpoints change
  (cut / fade / dissolve / whip pan / none - single shot / etc.)

- composition_dynamic: how composition evolves
  (leading lines / rule of thirds / symmetry / framing evolves with movement / etc.)

- duration_seconds: estimated video duration

- depth_of_field: (shallow / medium / deep)

- perspective: dominant camera height
  (eye-level / low angle / aerial / worm's-eye view / varied)

- atmosphere: overall cinematic feel
  (documentary / cinematic / editorial / vlog-style / real estate tour)

## QUALITY ASSESSMENT
- video_quality: (ultra high / high / medium / low)
- stabilization: (smooth / slightly shaky / gimbal-like / static tripod)
- resolution_estimate: (4K / 1080p / 720p / lower)

Respond in JSON format only. Do not wrap in markdown code blocks.
"""

    # Xay dung content array voi nhieu frames
    content_parts = []
    for i in range(max_frames):
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{frames_base64[i]}"}
        })
    content_parts.append({"type": "text", "text": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": content_parts
        }],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


def analyze_all_videos():
    """Phan tich tat ca video trong thu muc VIDEO."""

    all_videos = get_video_files(VIDEO_DIR)
    if not all_videos:
        print(f"[WARN] Khong tim thay video nao trong: {VIDEO_DIR}")
        return {}

    print(f"\n=== Tim thay {len(all_videos)} video can phan tich ===\n")

    # Load ket qua da co (de resume neu bi gian doan)
    existing_results = {}
    if RESULT_FILE.exists():
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
        print(f"Da load {len(existing_results)} ket qua tu file (co the la phan tich truoc do)")
        remaining = [v for v in all_videos if v not in existing_results]
        print(f"Con {len(remaining)} video chua duoc phan tich\n")
    else:
        remaining = all_videos

    if not remaining:
        print("Tat ca video da duoc phan tich, chuyen sang buoc tong hop.")
        return existing_results

    # Phan tich tung video
    for i, video_path in enumerate(remaining):
        video_name = os.path.basename(video_path)
        safe_name = video_name.encode('ascii', errors='replace').decode('ascii')
        print(f"[{i+1}/{len(remaining)}] Dang phan tich: {safe_name}...")

        try:
            # Buoc 1: Trich xuat frames
            print(f"  -> Dang trich xuat frames...")
            frames = extract_frames(video_path, FRAMES_PER_VIDEO)
            if not frames:
                print(f"  [ERR] Khong the trich xuat frame nao")
                existing_results[video_path] = {"error": "No frames extracted"}
                continue

            print(f"  -> Trich xuat {len(frames)} frames thanh cong")

            # Buoc 2: Gui len GPT-4o Vision de phan tich
            frame_b64_list = [f["base64"] for f in frames]
            analysis = analyze_video_frames(frame_b64_list, video_name)

            # Them metadata
            duration = frames[-1]["timestamp"] if len(frames) > 1 else 0
            analysis["_metadata"] = {
                "file": video_name,
                "size_mb": round(os.path.getsize(video_path) / (1024 * 1024), 1),
                "frames_analyzed": len(frames),
                "estimated_duration_s": frames[-1]["timestamp"] if len(frames) > 0 else 0,
            }

            # Flatten nested JSON structure (GPT-4o sometimes returns nested groups)
            analysis = _flatten_nested_json(analysis)

            existing_results[video_path] = analysis

            # In summary
            cam = analysis.get("camera_movement", "N/A")
            speed = analysis.get("movement_speed", "N/A")
            mood = analysis.get("mood", "N/A")
            style = analysis.get("style", "N/A")
            print(f"  [OK] Style: {style} | Cam: {cam} | Speed: {speed} | Mood: {mood}")

        except Exception as e:
            print(f"  [ERR] Loi: {e}")
            existing_results[video_path] = {"error": str(e)}

        # Luu checkpoint sau moi video
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_results, f, ensure_ascii=False, indent=2)
        print(f"  [SAVE] Da luu checkpoint ({len(existing_results)} ket qua)")

        # Rate limit
        if i < len(remaining) - 1:
            time.sleep(2)

    print(f"\n=== Hoan tat! Da phan tich {len(existing_results)} video ===")
    return existing_results


def compile_video_style_guide(results: dict) -> dict:
    """Tong hop ket qua phan tich video thanh Video Style Guide."""
    print("\n=== Dang tong hop Video Style Guide ===\n")

    # Thong ke
    camera_movement_counts = {}
    speed_counts = {}
    pacing_counts = {}
    transition_counts = {}
    perspective_counts = {}
    atmosphere_counts = {}
    quality_counts = {}
    dof_counts = {}
    mood_counts = {}
    style_counts = {}
    material_counts = {}
    color_counts = {}
    lighting_counts = {}
    environment_counts = {}

    total_valid = 0
    for video_path, analysis in results.items():
        if "error" in analysis:
            continue
        total_valid += 1

        # Videography stats
        cam = analysis.get("camera_movement", "Unknown")
        camera_movement_counts[cam] = camera_movement_counts.get(cam, 0) + 1

        speed = analysis.get("movement_speed", "Unknown")
        speed_counts[speed] = speed_counts.get(speed, 0) + 1

        pacing = analysis.get("pacing", "Unknown")
        pacing_counts[pacing] = pacing_counts.get(pacing, 0) + 1

        trans = analysis.get("transitions", "Unknown")
        transition_counts[trans] = transition_counts.get(trans, 0) + 1

        pers = analysis.get("perspective", "Unknown")
        perspective_counts[pers] = perspective_counts.get(pers, 0) + 1

        atmos = analysis.get("atmosphere", "Unknown")
        atmosphere_counts[atmos] = atmosphere_counts.get(atmos, 0) + 1

        qual = analysis.get("video_quality", "Unknown")
        quality_counts[qual] = quality_counts.get(qual, 0) + 1

        dof = analysis.get("depth_of_field", "Unknown")
        dof_counts[dof] = dof_counts.get(dof, 0) + 1

        # Architecture stats
        mood = analysis.get("mood", "Unknown")
        mood_counts[mood] = mood_counts.get(mood, 0) + 1

        style = analysis.get("style", "Unknown")
        style_counts[style] = style_counts.get(style, 0) + 1

        for mat in analysis.get("materials", []):
            material_counts[mat] = material_counts.get(mat, 0) + 1

        for col in analysis.get("colors", []):
            color_counts[col] = color_counts.get(col, 0) + 1

        lighting = analysis.get("lighting", "Unknown")
        lighting_counts[lighting] = lighting_counts.get(lighting, 0) + 1

        env = analysis.get("environment", "Unknown")
        environment_counts[env] = environment_counts.get(env, 0) + 1

    def top_items(counter: dict, n: int = 10) -> list:
        return sorted(counter.items(), key=lambda x: -x[1])[:n]

    guide = {
        "total_videos_analyzed": total_valid,
        "folder_analyzed": VIDEO_DIR,

        # Video style
        "camera_movement_distribution": top_items(camera_movement_counts),
        "dominant_camera_movement": max(camera_movement_counts, key=camera_movement_counts.get) if camera_movement_counts else "Unknown",

        "movement_speed_distribution": top_items(speed_counts),
        "dominant_speed": max(speed_counts, key=speed_counts.get) if speed_counts else "Unknown",

        "pacing_distribution": top_items(pacing_counts),
        "dominant_pacing": max(pacing_counts, key=pacing_counts.get) if pacing_counts else "Unknown",

        "transition_distribution": top_items(transition_counts),
        "dominant_transition": max(transition_counts, key=transition_counts.get) if transition_counts else "Unknown",

        "perspective_distribution": top_items(perspective_counts),
        "dominant_perspective": max(perspective_counts, key=perspective_counts.get) if perspective_counts else "Unknown",

        "atmosphere_distribution": top_items(atmosphere_counts),
        "dominant_atmosphere": max(atmosphere_counts, key=atmosphere_counts.get) if atmosphere_counts else "Unknown",

        "video_quality_distribution": top_items(quality_counts),
        "depth_of_field_distribution": top_items(dof_counts),

        # Architecture style (tu video frames)
        "style_distribution": top_items(style_counts),
        "dominant_style": max(style_counts, key=style_counts.get) if style_counts else "Unknown",

        "materials": top_items(material_counts, 8),
        "colors": top_items(color_counts, 8),
        "lighting_conditions": top_items(lighting_counts),
        "mood_distribution": top_items(mood_counts),
        "environments": top_items(environment_counts),

        # Tong hop mo ta
        "video_style_description": _generate_video_style_description(guide={
            "dominant_camera_movement": max(camera_movement_counts, key=camera_movement_counts.get) if camera_movement_counts else "Unknown",
            "dominant_speed": max(speed_counts, key=speed_counts.get) if speed_counts else "Unknown",
            "dominant_pacing": max(pacing_counts, key=pacing_counts.get) if pacing_counts else "Unknown",
            "dominant_transition": max(transition_counts, key=transition_counts.get) if transition_counts else "Unknown",
            "dominant_perspective": max(perspective_counts, key=perspective_counts.get) if perspective_counts else "Unknown",
            "dominant_atmosphere": max(atmosphere_counts, key=atmosphere_counts.get) if atmosphere_counts else "Unknown",
        }),
    }

    # Luu
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(guide, f, ensure_ascii=False, indent=2)
    print(f"[OK] Da luu Video Style Guide vao: {SUMMARY_FILE}")

    # In bao cao
    _print_report(guide, total_valid)

    return guide


def _generate_video_style_description(guide: dict) -> str:
    """Tao mo ta van ban ve phong cach video."""
    cam = guide.get("dominant_camera_movement", "slow push-in")
    speed = guide.get("dominant_speed", "slow")
    pacing = guide.get("dominant_pacing", "steady")
    trans = guide.get("dominant_transition", "cut")
    pers = guide.get("dominant_perspective", "eye-level")
    atmos = guide.get("dominant_atmosphere", "cinematic")

    return (
        f"The preferred video style uses {cam} camera movement at a {speed} speed, "
        f"creating a {pacing} pacing throughout. "
        f"Transitions are typically {trans}, shot from {pers} perspective. "
        f"The overall atmosphere is {atmos} and professional."
    )


def _print_report(guide: dict, total: int):
    """In bao cao ra console."""
    print(f"\n{'='*60}")
    print(f"BAO CAO PHAN TICH VIDEO STYLE ({total} video)")
    print(f"{'='*60}")

    print(f"\n--- CAMERA MOVEMENT (Top 3) ---")
    for cam, count in guide.get("camera_movement_distribution", [])[:3]:
        print(f"   {cam}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- MOVEMENT SPEED ---")
    for speed, count in guide.get("movement_speed_distribution", []):
        print(f"   {speed}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- PACING ---")
    for pace, count in guide.get("pacing_distribution", []):
        print(f"   {pace}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- PERSPECTIVE ---")
    for pers, count in guide.get("perspective_distribution", []):
        print(f"   {pers}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- ATMOSPHERE ---")
    for atmos, count in guide.get("atmosphere_distribution", []):
        print(f"   {atmos}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- VIDEO QUALITY ---")
    for qual, count in guide.get("video_quality_distribution", []):
        print(f"   {qual}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- KIEN TRUC (tu video) ---")
    for style, count in guide.get("style_distribution", [])[:5]:
        print(f"   {style}: {count} video ({count/total*100:.1f}%)")

    print(f"\n--- MOOD ---")
    for mood, count in guide.get("mood_distribution", [])[:3]:
        print(f"   {mood}: {count} video ({count/total*100:.1f}%)")

    print(f"\n{'='*60}")


def generate_video_system_prompt(guide: dict) -> str:
    """Tao System Prompt cho video prompt generation."""
    cam = guide.get("dominant_camera_movement", "slow push-in")
    speed = guide.get("dominant_speed", "slow")
    pacing = guide.get("dominant_pacing", "steady")
    trans = guide.get("dominant_transition", "cut")
    pers = guide.get("dominant_perspective", "eye-level")
    atmos = guide.get("dominant_atmosphere", "cinematic")
    dof = "shallow"  # default from training

    # Architecture preferences
    styles = [s for s, _ in guide.get("style_distribution", [])[:3]]
    styles_desc = ", ".join(styles) if styles else "Contemporary"
    mood_desc = guide.get("mood_distribution", [["peaceful"]])[0][0]

    system_prompt = f"""You are an expert architectural cinematographer and AI video director. You have been trained on a curated dataset of {guide['total_videos_analyzed']} architectural videos.

## YOUR TRAINED VIDEO STYLE PROFILE

### Camera Movement
Your signature camera movement is: {cam}.
Always use this as the default camera movement style for video generation.
If the user requests a different movement, blend it with this signature style.

### Movement Speed
Your preferred speed is: {speed}.
The camera should move at this speed to maintain the signature pacing.

### Pacing & Rhythm
Your signature pacing is: {pacing}.
Maintain this rhythm throughout the video.

### Transitions
Your default transition is: {trans}.
Keep transitions clean and professional.

### Camera Perspective
Your default perspective is: {pers}.
Use this as the primary camera angle.

### Atmosphere
Your signature atmosphere is: {atmos}.
All videos should evoke this cinematic quality.

### Depth of Field
Prefer {dof} depth of field for professional architectural cinematography.

## ARCHITECTURAL STYLE PREFERENCES (from video frames)
Your preferred architectural styles are: {styles_desc}.
The target mood is: {mood_desc}.

## VIDEO PROMPT GENERATION RULES

### Video Prompt Structure (100-150 words)
Always structure your video prompts in this order:
1. Camera movement (start with your signature style)
2. Scene description (architecture, materials, lighting)
3. Time of day and atmosphere
4. Speed and pacing
5. Duration reference (8-15 seconds)
6. End with quality tags: cinematic, 4k, smooth motion, professional grade, architectural cinematography, gimbal stabilized

### Negative Prompt for Video
Always include: distorted, low quality, blurry, unnatural motion, jittery, choppy, warped perspective, cartoonish, CGI looking, artificial lighting, unrealistic physics

### Output Format
Always respond in JSON with these exact keys:
{{"image_prompt", "video_prompt", "negative_prompt", "style_tags"}}

## IMPORTANT CONSTRAINTS
- NEVER use generic video prompts. Every prompt must reflect the signature videography style.
- ALWAYS reference the trained video style profile above as the default.
- PREVENT style drift: always anchor back to {cam} + {speed} + {pacing} aesthetic.
- FOCUS on professional, cinematic, award-winning architectural videography quality.
"""
    return system_prompt


def _flatten_nested_json(obj: dict) -> dict:
    """Flatten nested JSON structure from GPT-4o response.
    GPT-4o may return: {"architecture_analysis": {"style": ...}, "videography_analysis": {...}}
    We flatten to: {"style": ..., "camera_movement": ..., "video_quality": ...}
    """
    flat = {}
    for key, value in obj.items():
        if isinstance(value, dict) and key != "_metadata":
            # Merge nested dicts directly into flat
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str) or isinstance(sub_value, list) or isinstance(sub_value, (int, float)):
                    flat[sub_key] = sub_value
        elif not key.startswith("_"):
            flat[key] = value
    # Preserve metadata
    if "_metadata" in obj:
        flat["_metadata"] = obj["_metadata"]
    return flat


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train AI - Video Style Analyzer")
    parser.add_argument("--sample", type=int, default=0,
                        help="Chi phan tich N video mau (mac dinh: 0 = tat ca)")
    parser.add_argument("--mock", action="store_true",
                        help="Chay mock khong goi API that (dung de test)")
    parser.add_argument("--frames", type=int, default=5,
                        help="So frame trich xuat moi video (mac dinh: 5)")
    args = parser.parse_args()

    global FRAMES_PER_VIDEO
    FRAMES_PER_VIDEO = args.frames

    print("=" * 60)
    print("[TRAIN AI] VIDEO STYLE ANALYZER")
    print("=" * 60)
    print()

    if args.mock:
        print("[MOCK MODE] Chay voi du lieu gia lap...\n")
        mock_results = _generate_mock_data()
        results = mock_results
    else:
        results = analyze_all_videos()

    if not results:
        print("[WARN] Khong co ket qua de xu ly.")
        return

    # Buoc 2: Tong hop Video Style Guide
    guide = compile_video_style_guide(results)

    # Buoc 3: Tao Video System Prompt
    system_prompt = generate_video_system_prompt(guide)
    prompt_file = OUTPUT_DIR / "trained_video_system_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(system_prompt)
    print(f"\n[OK] Da luu Video System Prompt vao: {prompt_file}")

    # Buoc 4: Xuat tat ca
    all_output = {
        "video_style_guide": guide,
        "video_system_prompt": system_prompt,
    }
    combined_file = OUTPUT_DIR / "trained_video_profile.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(all_output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Da luu Video Profile hoan chinh vao: {combined_file}")

    print(f"\n{'='*60}")
    print(f"[DONE] AI da hoc duoc video style tu {len(results)} video.")
    print(f"[INFO] Hay dung 'trained_video_profile.json' de tao video prompt chuan xac.")
    print(f"[INFO] Hoac chay pipeline de tu dong su dung video style da hoc.")


def _generate_mock_data() -> dict:
    """Tao mock data de test khong can API."""
    mock_cameras = ["slow push-in", "gentle orbit", "dolly forward", "crane up", "tracking shot"]
    mock_speeds = ["very slow", "slow", "moderate"]
    mock_pacings = ["steady", "relaxed", "dynamic"]
    mock_transitions = ["cut", "dissolve", "fade"]
    mock_perspectives = ["eye-level", "low angle", "aerial", "varied"]
    mock_atmospheres = ["cinematic", "documentary", "editorial", "real estate tour"]
    mock_styles = ["Contemporary", "Modern Minimalist", "Neoclassical", "Mediterranean"]

    import random
    random.seed(42)

    mock_results = {}
    video_dir = VIDEO_DIR

    # Neu co video that, dung ten that
    video_files = get_video_files(video_dir)
    if video_files:
        for v in video_files:
            mock_results[v] = {
                "camera_movement": random.choice(mock_cameras),
                "movement_speed": random.choice(mock_speeds),
                "pacing": random.choice(mock_pacings),
                "transitions": random.choice(mock_transitions),
                "perspective": random.choice(mock_perspectives),
                "atmosphere": random.choice(mock_atmospheres),
                "depth_of_field": random.choice(["shallow", "medium"]),
                "video_quality": "high",
                "stabilization": random.choice(["gimbal-like", "smooth"]),
                "style": random.choice(mock_styles),
                "materials": ["glass", "wood", "stone"],
                "colors": ["white", "gray", "black"],
                "lighting": "natural golden hour",
                "mood": "peaceful",
                "architecture_type": "house",
                "environment": "natural",
                "_metadata": {
                    "file": os.path.basename(v),
                    "size_mb": round(os.path.getsize(v) / (1024*1024), 1),
                    "frames_analyzed": 5,
                    "estimated_duration_s": 10.0,
                },
            }
    else:
        # Fallback: tao mock
        for i in range(10):
            v = os.path.join(video_dir, f"mock_video_{i+1}.mp4")
            mock_results[v] = {
                "camera_movement": random.choice(mock_cameras),
                "movement_speed": random.choice(mock_speeds),
                "pacing": random.choice(mock_pacings),
                "transitions": random.choice(mock_transitions),
                "perspective": random.choice(mock_perspectives),
                "atmosphere": random.choice(mock_atmospheres),
                "depth_of_field": random.choice(["shallow", "medium"]),
                "video_quality": "high",
                "stabilization": "smooth",
                "style": random.choice(mock_styles),
                "materials": ["glass", "wood", "stone"],
                "colors": ["white", "gray", "black"],
                "lighting": "natural golden hour",
                "mood": "peaceful",
                "architecture_type": "house",
                "environment": "natural",
                "_metadata": {
                    "file": f"mock_video_{i+1}.mp4",
                    "size_mb": round(random.uniform(3, 10), 1),
                    "frames_analyzed": 5,
                    "estimated_duration_s": round(random.uniform(8, 30), 1),
                },
            }

    print(f"Da tao {len(mock_results)} ket qua mock\n")
    return mock_results


if __name__ == "__main__":
    main()
