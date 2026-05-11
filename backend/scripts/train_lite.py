"""
TRAIN LITE — Phan tich toan bo anh TRAIN AI bang Pillow (da co san).
KHONG can API key, KHONG can model.
Chi phan tich: mau sac, do sang, aspect ratio, texture don gian.

Chay: python backend/scripts/train_lite.py
"""

import sys
import os
import json
import math
from pathlib import Path
from collections import Counter
from PIL import Image, ImageStat, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ======================== PATHS ========================
TRAIN_DIRS = [
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "1"),
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "2"),
]
OUTPUT_DIR = Path(__file__).parent / "training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_FILE = OUTPUT_DIR / "trained_style_profile.json"
PROMPT_FILE = OUTPUT_DIR / "trained_system_prompt.txt"

# ======================== COLOR NAMES ========================
COLOR_NAMES = {
    "#000000": "black", "#1a1a2e": "midnight blue", "#2d2d2d": "dark charcoal",
    "#3d3d3d": "charcoal", "#4a4a4a": "dark gray", "#555555": "medium gray",
    "#666666": "gray", "#777777": "silver gray", "#888888": "light gray",
    "#999999": "pale gray", "#aaaaaa": "light silver", "#cccccc": "off-white",
    "#ffffff": "white",
}

def hex_to_name(hex_code: str) -> str:
    """Convert hex to nearest named color."""
    hex_code = hex_code.lower()
    if hex_code in COLOR_NAMES:
        return COLOR_NAMES[hex_code]
    
    r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
    
    # Warm tones
    if r > g + 30 and r > b + 30:
        if r > 200: return "warm red / terracotta"
        if r > 150: return "brick red"
        return "dark red"
    if r > 180 and g > 120 and b < 100:
        return "warm orange / terra"
    
    # Cool tones  
    if b > r + 20 and b > g + 20:
        if b > 200: return "cool blue"
        if b > 140: return "steel blue"
        return "navy blue"
    
    # Green tones
    if g > r + 20 and g > b + 20:
        if g > 180: return "fresh green"
        if g > 120: return "olive green"
        return "forest green"
    
    # Neutral/warm neutrals
    if abs(r - g) < 25 and abs(g - b) < 25:
        brightness = (r + g + b) / 3
        if brightness > 230: return "white"
        if brightness > 200: return "off-white / cream"
        if brightness > 170: return "light beige"
        if brightness > 140: return "warm beige"
        if brightness > 110: return "taupe / greige"
        if brightness > 80: return "medium brown"
        if brightness > 50: return "dark brown"
        return "deep brown / espresso"
    
    # Yellow tones
    if r > 180 and g > 180 and b < 100:
        return "golden yellow"
    
    return f"#{r:02x}{g:02x}{b:02x}"


def get_image_files(directory: str) -> list[str]:
    """Lay tat ca file anh, bo qua AI-enhanced."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    ai_keywords = ['beautyplus', 'picsart', 'aiimageenhancer', 'enhancer']
    files, skipped = [], 0
    for f in os.listdir(directory):
        ext = os.path.splitext(f)[1].lower()
        if ext not in valid_exts:
            continue
        if any(kw in f.lower() for kw in ai_keywords):
            skipped += 1
            continue
        files.append(os.path.join(directory, f))
    if skipped:
        print(f"  [FILTER] Bo qua {skipped} anh AI-enhanced")
    return sorted(files)


def analyze_colors_advanced(image: Image.Image) -> dict:
    """Phan tich mau sac nang cao: dominant palette + warmth + saturation."""
    img = image.resize((150, 150))
    
    # Quantize to 16 colors
    quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    
    # Count colors
    color_counts = Counter(quantized.getdata())
    total_pixels = sum(color_counts.values())
    
    colors = []
    for idx, count in color_counts.most_common(8):
        r, g, b = palette[idx*3], palette[idx*3+1], palette[idx*3+2]
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        name = hex_to_name(hex_code)
        pct = count / total_pixels
        colors.append({"hex": hex_code, "name": name, "rgb": [r, g, b], "pct": round(pct, 4)})
    
    # Warmth analysis
    warm_pct = sum(c["pct"] for c in colors if c["rgb"][0] > c["rgb"][2] + 15)
    cool_pct = sum(c["pct"] for c in colors if c["rgb"][2] > c["rgb"][0] + 15)
    neutral_pct = 1 - warm_pct - cool_pct
    
    # Is it monochrome? (low saturation)
    saturations = []
    for c in colors:
        rgb = c["rgb"]
        max_c = max(rgb)
        min_c = min(rgb)
        sat = (max_c - min_c) / max(max_c, 1)
        saturations.append(sat)
    avg_saturation = sum(s * c["pct"] for s, c in zip(saturations, colors))
    
    return {
        "dominant_colors": colors[:6],
        "warmth": {"warm": round(warm_pct, 3), "cool": round(cool_pct, 3), "neutral": round(neutral_pct, 3)},
        "is_monochrome": avg_saturation < 0.15,
        "avg_saturation": round(avg_saturation, 3),
        "is_warm_dominant": warm_pct > 0.4,
        "is_cool_dominant": cool_pct > 0.4,
    }


def analyze_texture(image: Image.Image) -> dict:
    """Phan tich texture don gian bang edge detection."""
    gray = image.convert("L").resize((200, 200))
    
    # Edge detection (difference from blurred)
    blurred = gray.filter(ImageFilter.GaussianBlur(radius=3))
    
    # Calculate "texture complexity" = how different edge is from blur
    edge_pixels = []
    for x in range(200):
        for y in range(200):
            edge_pixels.append(abs(gray.getpixel((x, y)) - blurred.getpixel((x, y))))
    
    avg_edge = sum(edge_pixels) / len(edge_pixels)
    
    # Many edges = detailed texture (stone, brick), few edges = smooth (glass, concrete)
    if avg_edge > 25:
        texture_type = "highly textured (stone/brick/wood grain)"
    elif avg_edge > 12:
        texture_type = "moderately textured (painted surfaces/metal)"
    else:
        texture_type = "smooth (glass/concrete/stucco)"
    
    return {
        "texture_complexity": round(avg_edge, 1),
        "texture_type": texture_type,
    }


def analyze_one_image(image_path: str, folder_name: str) -> dict:
    """Phan tich toan dien mot anh."""
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        return None
    
    # Colors
    color_data = analyze_colors_advanced(image)
    
    # Texture
    texture = analyze_texture(image)
    
    # Brightness & contrast
    stat = ImageStat.Stat(image)
    brightness = sum(stat.mean) / len(stat.mean)
    contrast = sum(stat.stddev) / len(stat.stddev)
    
    # Dimensions
    w, h = image.size
    aspect = round(w / h, 2)
    
    # Determine lighting
    if brightness > 180:
        lighting = "bright daylight"
    elif brightness > 130:
        lighting = "natural moderate"
    elif brightness > 80:
        lighting = "soft dim / twilight"
    else:
        lighting = "night / dramatic interior"
    
    # Determine mood from brightness + warmth
    if brightness > 150 and color_data["is_warm_dominant"]:
        mood = "warm & inviting"
    elif brightness > 150:
        mood = "bright & airy"
    elif brightness > 100:
        mood = "peaceful & serene"
    elif color_data["is_warm_dominant"]:
        mood = "cozy & intimate"
    else:
        mood = "dramatic & moody"
    
    # Determine environment from aspect ratio + brightness
    if aspect > 1.5:
        env = "wide landscape / suburban"
    elif aspect > 1.2:
        env = "natural / garden setting"
    else:
        env = "urban / architectural"
    
    # Materials guess
    materials = []
    if texture["texture_complexity"] < 12:
        materials.append("glass")
        materials.append("smooth concrete")
    elif texture["texture_complexity"] < 25:
        materials.append("steel")
        materials.append("painted surface")
    else:
        materials.append("natural stone")
        materials.append("wood")
    
    if color_data["is_monochrome"]:
        materials.append("white stucco / plaster")
    if color_data["is_warm_dominant"]:
        materials.append("warm wood / terracotta")
    
    # Features guess
    features = ["large windows", "clean lines"]
    if aspect > 1.3:
        features.append("expansive horizontal layout")
    if brightness > 150:
        features.append("natural light filled")
    
    return {
        "style": "Contemporary",
        "materials": materials[:4],
        "colors": [c["name"] for c in color_data["dominant_colors"]],
        "colors_hex": [c["hex"] for c in color_data["dominant_colors"]],
        "lighting": lighting,
        "mood": mood,
        "environment": env,
        "key_features": features,
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "aspect_ratio": aspect,
        "dimensions": f"{w}x{h}",
        "texture": texture["texture_type"],
        "file": os.path.basename(image_path),
    }


def create_style_summary(results: list[dict]) -> dict:
    """Tao style guide tu ket qua phan tich."""
    materials = Counter()
    colors = Counter()
    lightings = Counter()
    moods = Counter()
    environments = Counter()
    features = Counter()
    textures = Counter()
    
    for r in results:
        if not r:
            continue
        for m in r.get("materials", []):
            materials[m] += 1
        for c in r.get("colors", []):
            colors[c] += 1
        lightings[r.get("lighting", "natural")] += 1
        moods[r.get("mood", "peaceful")] += 1
        environments[r.get("environment", "urban")] += 1
        for f in r.get("key_features", []):
            features[f] += 1
        textures[r.get("texture", "smooth")] += 1
    
    total = len([r for r in results if r])
    
    return {
        "total_images_analyzed": total,
        "analysis_method": "color + texture + brightness (Pillow, no API)",
        "dominant_style": "Contemporary",
        "style_distribution": [["Contemporary", total]],
        "top_materials": [m for m, _ in materials.most_common(6)],
        "primary_palette": [c for c, _ in colors.most_common(8)],
        "dominant_lighting": lightings.most_common(1)[0][0] if lightings else "natural",
        "dominant_mood": moods.most_common(1)[0][0] if moods else "peaceful",
        "dominant_environment": environments.most_common(1)[0][0] if environments else "landscape",
        "top_key_features": [f for f, _ in features.most_common(8)],
        "texture_profile": [t for t, _ in textures.most_common(3)],
        "lighting_distribution": lightings.most_common(5),
        "mood_distribution": moods.most_common(5),
        "environment_distribution": environments.most_common(5),
    }


def generate_system_prompt(guide: dict) -> str:
    """Tao system prompt tu style guide."""
    mats = guide.get("top_materials", [])
    cols = guide.get("primary_palette", [])
    lighting = guide.get("dominant_lighting", "natural")
    mood = guide.get("dominant_mood", "peaceful")
    env = guide.get("dominant_environment", "landscape")
    features = guide.get("top_key_features", [])
    total = guide.get("total_images_analyzed", 0)
    
    return f"""You are an expert architectural photographer and AI art director. 
You have analyzed {total} architectural reference images to learn the user's style.

## TRAINED STYLE PROFILE

### Preferred Materials
{', '.join(mats[:5])}

### Signature Color Palette  
{', '.join(cols[:6])}

### Lighting
{lighting}

### Mood
{mood}

### Environment
{env}

### Key Features
{', '.join(features[:6])}

## PROMPT GENERATION RULES

### Image Prompt (200 words max)
1. Architecture style: Contemporary
2. Materials: {', '.join(mats[:4])}
3. Colors: {', '.join(cols[:5])}
4. Lighting: {lighting}
5. Mood: {mood}
6. Environment: {env}
7. Quality: ultra realistic, architectural photography, 8k, professional, HDR

### Negative Prompt
distorted, low quality, blurry, unnatural colors, cartoonish, oversaturated, warped perspective

### Output Format
JSON: {{"image_prompt": "...", "video_prompt": "...", "negative_prompt": "...", "style_tags": [...]}}
"""


def main():
    print("=" * 60)
    print("TRAIN LITE — Pillow Color + Texture Analysis")
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
            result = analyze_one_image(img_path, folder_name)
            if result:
                all_results.append(result)
                print(f"  [{i+1}/{len(images)}] {img_name} -> {result['mood']} | {result['lighting']}")
    
    if not all_results:
        print("\n[ERROR] Khong co anh nao de phan tich!")
        return
    
    # Generate style guide
    print(f"\n=== Tong hop {len(all_results)} anh ===")
    style_guide = create_style_summary(all_results)
    
    # Save profile
    profile = {"style_guide": style_guide}
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVE] {PROFILE_FILE}")
    
    # Generate system prompt
    prompt = generate_system_prompt(style_guide)
    with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"[SAVE] {PROMPT_FILE}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("✅ TRAINING HOAN THANH!")
    print(f"   Tong anh: {style_guide['total_images_analyzed']}")
    print(f"   Mau sac: {', '.join(style_guide['primary_palette'][:4])}")
    print(f"   Vat lieu: {', '.join(style_guide['top_materials'])}")
    print(f"   Anh sang: {style_guide['dominant_lighting']}")
    print(f"   Khong gian: {style_guide['dominant_mood']}")
    print(f"   Moi truong: {style_guide['dominant_environment']}")
    print(f"   Dac diem: {', '.join(style_guide['top_key_features'][:5])}")
    print("=" * 60)
    
    return style_guide


if __name__ == "__main__":
    main()
