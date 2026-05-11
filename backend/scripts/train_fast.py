"""
Train Analyzer FAST — Khong can API key, khong can CLIP.
Chi dung Pillow + NumPy de phan tich mau sac, do sang, kich thuoc.
Phan loai style dua tren ten file + thu muc.

Chay: python backend/scripts/train_fast.py
"""

import sys
import os
import json
import math
from pathlib import Path
from collections import Counter
from PIL import Image, ImageStat

# Them backend vao sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Architecture style keywords mapped to file/folder names
STYLE_KEYWORDS = {
    "Contemporary": ["contemporary", "modern", "hien dai", "đương đại"],
    "Modern Minimalist": ["minimalist", "minimal", "tối giản", "don gian", "đơn giản"],
    "Neoclassical": ["neoclassical", "classical", "cổ điển", "tan co dien", "tân cổ điển"],
    "Mediterranean": ["mediterranean", "spanish", "italian", "địa trung hải"],
    "Industrial": ["industrial", "loft", "công nghiệp", "factory"],
    "Tropical": ["tropical", "resort", "nhiệt đới", "balinese"],
    "Scandinavian": ["scandinavian", "nordic", "bắc âu"],
    "Japanese Zen": ["japanese", "zen", "nhật", "nhat"],
    "Brutalist": ["brutalist", "brutalism", "concrete"],
    "Modern Farmhouse": ["farmhouse", "rustic", "nông thôn"],
}

# ======================== PATHS ========================

TRAIN_DIRS = [
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "1"),
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "2"),
]

OUTPUT_DIR = Path(__file__).parent / "training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_FILE = OUTPUT_DIR / "trained_style_profile.json"
PROMPT_FILE = OUTPUT_DIR / "trained_system_prompt.txt"


def get_image_files(directory: str) -> list[str]:
    """Lay tat ca file anh, bo qua AI-enhanced."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    ai_enhanced_keywords = ['beautyplus', 'picsart', 'aiimageenhancer', 'enhancer']
    files = []
    skipped = 0
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext not in valid_exts:
            continue
        f_lower = f.lower()
        if any(kw in f_lower for kw in ai_enhanced_keywords):
            skipped += 1
            continue
        files.append(os.path.join(directory, f))
    if skipped > 0:
        print(f"  [FILTER] Bo qua {skipped} anh AI-enhanced trong {directory}")
    return sorted(files)


def guess_style(filepath: str, folder_name: str) -> str:
    """Doan style dua tren ten file + ten thu muc."""
    full_path_lower = filepath.lower()
    
    # Check folder name first
    if folder_name.lower() in STYLE_KEYWORDS:
        return STYLE_KEYWORDS[folder_name.lower()][0]
    
    # Check file path keywords
    for style, keywords in STYLE_KEYWORDS.items():
        for kw in keywords:
            if kw in full_path_lower:
                return style
    
    return "Contemporary"  # default


def analyze_colors(image: Image.Image) -> dict:
    """Phan tich mau sac bang color quantization don gian."""
    # Resize nho de xu ly nhanh
    img = image.resize((100, 100))
    
    # Lay cac mau pho bien nhat
    pixels = list(img.getdata())
    color_counter = Counter(pixels)
    top_colors = color_counter.most_common(10)
    
    # Convert to hex
    colors = []
    for rgb, count in top_colors:
        r, g, b = rgb[0], rgb[1], rgb[2]
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        pct = count / len(pixels)
        colors.append({"hex": hex_code, "rgb": [r, g, b], "pct": round(pct, 4)})
    
    # Xac dinh tone chinh
    warm_count = sum(c["pct"] for c in colors if c["rgb"][0] > c["rgb"][2] + 20)
    cool_count = sum(c["pct"] for c in colors if c["rgb"][2] > c["rgb"][0] + 20)
    
    return {
        "dominant_colors": colors[:5],
        "is_warm": warm_count > cool_count,
        "is_cool": cool_count > warm_count,
    }


def analyze_image_fast(image_path: str, folder_name: str) -> dict:
    """Phan tich nhanh mot anh."""
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        return None
    
    # Style guess
    style = guess_style(image_path, folder_name)
    
    # Colors
    color_data = analyze_colors(image)
    
    # Brightness & contrast
    stat = ImageStat.Stat(image)
    brightness = sum(stat.mean) / len(stat.mean)
    contrast = sum(stat.stddev) / len(stat.stddev)
    
    # Aspect ratio
    w, h = image.size
    aspect = round(w / h, 2)
    
    # Guessing lighting based on brightness
    if brightness > 180:
        lighting = "bright daylight"
    elif brightness > 130:
        lighting = "natural moderate"
    elif brightness > 80:
        lighting = "soft dim / twilight"
    else:
        lighting = "night / dramatic"
    
    # Guessing materials from colors
    materials = ["glass", "concrete"]
    if color_data["is_warm"]:
        materials.append("wood")
    if not color_data["is_warm"] and not color_data["is_cool"]:
        materials.append("stone")
    materials.append("steel")
    
    result = {
        "style": style,
        "materials": materials,
        "colors": [c["hex"] for c in color_data["dominant_colors"]],
        "lighting": lighting,
        "mood": "peaceful" if brightness > 100 else "dramatic",
        "environment": "landscape" if aspect > 1.3 else "urban",
        "key_features": ["large windows", "clean lines", "modern design"],
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "aspect_ratio": aspect,
        "dimensions": f"{w}x{h}",
    }
    
    return result


def create_summary(all_results: list[dict]) -> dict:
    """Tao style summary."""
    styles = Counter()
    materials = Counter()
    colors = Counter()
    lightings = Counter()
    moods = Counter()
    environments = Counter()
    features = Counter()
    
    for r in all_results:
        if not r:
            continue
        styles[r.get("style", "Unknown")] += 1
        moods[r.get("mood", "Unknown")] += 1
        lightings[r.get("lighting", "Unknown")] += 1
        environments[r.get("environment", "Unknown")] += 1
        for m in r.get("materials", []):
            materials[m] += 1
        for c in r.get("colors", []):
            colors[c] += 1
        for f in r.get("key_features", []):
            features[f] += 1
    
    total = len([r for r in all_results if r])
    
    return {
        "total_images_analyzed": total,
        "style_distribution": styles.most_common(10),
        "dominant_style": styles.most_common(1)[0][0] if styles else "Contemporary",
        "materials": materials.most_common(15),
        "top_materials": [m for m, _ in materials.most_common(6)],
        "colors": colors.most_common(15),
        "primary_palette": [c for c, _ in colors.most_common(6)],
        "lighting_distribution": lightings.most_common(5),
        "dominant_lighting": lightings.most_common(1)[0][0] if lightings else "natural",
        "mood_distribution": moods.most_common(5),
        "dominant_mood": moods.most_common(1)[0][0] if moods else "peaceful",
        "environment_distribution": environments.most_common(5),
        "dominant_environment": environments.most_common(1)[0][0] if environments else "landscape",
        "top_key_features": [f for f, _ in features.most_common(8)],
    }


def generate_prompt(style_guide: dict) -> str:
    """Tao system prompt tu style guide."""
    styles = [s for s, _ in style_guide.get("style_distribution", [])[:4]]
    materials = style_guide.get("top_materials", [])
    colors = style_guide.get("primary_palette", [])
    lighting = style_guide.get("dominant_lighting", "natural")
    mood = style_guide.get("dominant_mood", "peaceful")
    features = style_guide.get("top_key_features", [])
    
    return f"""You are an expert architectural photographer and AI art director.
You have been trained on a curated dataset of {style_guide.get('total_images_analyzed', 0)} architectural images.

## TRAINED STYLE PROFILE

### Dominant Architectural Styles
The user's preferred styles: {', '.join(styles)}.
Always favor these styles when generating prompts.

### Preferred Materials
Typical materials: {', '.join(materials)}.
Incorporate these materials naturally.

### Color Palette
Signature colors: {', '.join(colors)}.
Ensure color harmony follows this palette.

### Lighting Preferences
Default lighting: {lighting}.

### Emotional Tone
Target mood: {mood}.
All generations should evoke this emotional quality.

### Key Features
{', '.join(features)}.

## PROMPT GENERATION RULES

### Image Prompt (max 200 words)
1. Architectural style + type
2. Materials + colors
3. Lighting + time of day
4. Camera angle
5. Atmosphere + mood
6. Environment context
7. Quality tags: ultra realistic, architectural photography, 8k, professional

### Negative Prompt
Always include: distorted, low quality, blurry, unnatural colors, cartoonish, oversaturated, warped perspective

### Output Format
JSON: {{"image_prompt", "video_prompt", "negative_prompt", "style_tags"}}
"""


def main():
    print("=" * 60)
    print("TRAIN FAST — Color + Brightness Analysis (No API)")
    print("=" * 60)
    
    all_results = []
    
    for dir_path in TRAIN_DIRS:
        if not os.path.exists(dir_path):
            print(f"[WARN] Thu muc khong ton tai: {dir_path}")
            continue
        
        folder_name = os.path.basename(dir_path)
        images = get_image_files(dir_path)
        print(f"\n[{folder_name}] {len(images)} anh")
        
        for i, img_path in enumerate(images):
            img_name = os.path.basename(img_path)[:50]
            result = analyze_image_fast(img_path, folder_name)
            if result:
                all_results.append(result)
                print(f"  [{i+1}/{len(images)}] {img_name} -> {result['style']} | {result['lighting']}")
    
    print(f"\n=== Tao style profile tu {len(all_results)} anh ===")
    
    style_guide = create_summary(all_results)
    
    # Save profile
    style_profile = {"style_guide": style_guide}
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(style_profile, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {PROFILE_FILE}")
    
    # Save prompt
    prompt = generate_prompt(style_guide)
    with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"[SAVE] {PROMPT_FILE}")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print(f"   Images: {style_guide['total_images_analyzed']}")
    print(f"   Style: {style_guide['dominant_style']}")
    print(f"   Colors: {', '.join(style_guide['primary_palette'][:4])}")
    print(f"   Mood: {style_guide['dominant_mood']}")
    print(f"   Lighting: {style_guide['dominant_lighting']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
