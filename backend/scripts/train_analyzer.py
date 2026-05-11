"""
Train Analyzer: Phan tich toan bo anh trong thu muc TRAIN AI de hoc style.
Su dung StyleAnalyzer (GPT-4o Vision) de phan tich tung anh.
"""

import sys
import os
import json
import base64
import time
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
# Debug: kiem tra API key da duoc load chua
print(f"[DEBUG] OPENAI_API_KEY set: {'OPENAI_API_KEY' in os.environ and len(os.environ['OPENAI_API_KEY']) > 20}")
print(f"[DEBUG] DEEPSEEK_API_KEY set: {'DEEPSEEK_API_KEY' in os.environ and len(os.environ['DEEPSEEK_API_KEY']) > 10}")

# Khong dung StyleAnalyzer tu services vi no load trained style (vong lap phu thuoc)
# Thay vao do, dung OpenAI truc tiep
from openai import OpenAI


TRAIN_DIRS = [
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "1"),
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "2"),
]

OUTPUT_DIR = Path(__file__).parent / "training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# File luu ket qua
RESULT_FILE = OUTPUT_DIR / "analysis_results.json"
SUMMARY_FILE = OUTPUT_DIR / "style_summary.json"


def get_image_files(directory: str) -> list[str]:
    """Lay tat ca file anh trong thu muc, bo qua anh AI-enhanced."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    # Bo qua anh da qua AI enhancement (BeautyPlus, Picsart, AiImageEnhancer)
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


def analyze_one_image(image_base64: str) -> dict:
    """Phan tich mot anh bang GPT-4o Vision."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment or .env file")

    client = OpenAI(api_key=api_key)

    prompt = """
    Analyze this architecture image and extract:
    - style: (Modern Minimalist / Contemporary / Industrial / Brutalist / Neoclassical / etc.)
    - materials: list of visible materials (concrete, glass, wood, steel, stone, etc.)
    - colors: primary color palette (list of hex codes or color names)
    - lighting: lighting conditions (natural, warm, cool, dramatic, soft, etc.)
    - mood: emotional tone (peaceful, dramatic, luxurious, cozy, futuristic, etc.)
    - architecture_type: (house / commercial / interior / landscape / urban / etc.)
    - environment: surrounding context (urban, suburban, natural, waterfront, etc.)
    - key_features: list of distinctive architectural features

    Respond in JSON format only. Do not wrap in markdown code blocks.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                },
                {"type": "text", "text": prompt}
            ]
        }],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


def analyze_all_images(sample: int = 0):

    # Thu thap tat ca file anh
    all_images = []
    for dir_path in TRAIN_DIRS:
        if os.path.exists(dir_path):
            images = get_image_files(dir_path)
            all_images.extend(images)
            print(f"[{dir_path}] Tim thay {len(images)} anh")
        else:
            print(f"[WARN] Thu muc khong ton tai: {dir_path}")

    # Gioi han so anh neu sample > 0
    if sample > 0 and sample < len(all_images):
        import random
        random.seed(42)
        all_images = random.sample(all_images, sample)
        print(f"\n=== Lay mau {sample} anh (ngau nhien) ===")
    else:
        print(f"\n=== Tong cong: {len(all_images)} anh can phan tich ===\n")

    # Load ket qua da co (phong khi bi gian doan)
    existing_results = {}
    if RESULT_FILE.exists():
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
        print(f"Da load {len(existing_results)} ket qua tu file (co the la phan tich truoc do)")
        # Chi phan tich nhung anh chua co ket qua
        remaining = [img for img in all_images if img not in existing_results]
        print(f"Con {len(remaining)} anh chua duoc phan tich\n")
    else:
        remaining = all_images

    if not remaining:
        print("Tat ca anh da duoc phan tich, chuyen sang buoc tong hop.")
        return existing_results

    # Phan tich tung anh
    for i, img_path in enumerate(remaining):
        img_name = os.path.basename(img_path)
        folder_name = os.path.basename(os.path.dirname(img_path))
        safe_name = img_name.encode('ascii', errors='replace').decode('ascii')
        safe_folder = folder_name.encode('ascii', errors='replace').decode('ascii')
        print(f"[{i+1}/{len(remaining)}] Dang phan tich: {safe_folder}/{safe_name}...")

        try:
            with open(img_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            analysis = analyze_one_image(image_base64)
            existing_results[img_path] = analysis
            print(f"  [OK] Style: {analysis.get('style', 'N/A')} | Mood: {analysis.get('mood', 'N/A')}")

        except Exception as e:
            print(f"  [ERR] Loi: {e}")
            existing_results[img_path] = {"error": str(e)}

        # Luu sau moi 5 anh (phong crash)
        if (i + 1) % 5 == 0 or i == len(remaining) - 1:
            with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_results, f, ensure_ascii=False, indent=2)
            print(f"  [SAVE] Da luu checkpoint ({len(existing_results)} ket qua)")

        # Rate limit: tranh bi API gioi han
        if i < len(remaining) - 1:
            time.sleep(1)

    print(f"\n=== Hoan tat! Da phan tich {len(existing_results)} anh ===")
    return existing_results


def compile_style_guide(results: dict) -> dict:
    """Tong hop ket qua phan tich thanh Style Guide tong quan."""
    print("\n=== Dang tong hop Style Guide ===\n")

    style_counts = {}
    material_counts = {}
    color_counts = {}
    lighting_counts = {}
    mood_counts = {}
    arch_type_counts = {}
    environment_counts = {}
    key_features_counts = {}

    total_valid = 0
    for img_path, analysis in results.items():
        if "error" in analysis:
            continue
        total_valid += 1

        # Style
        style = analysis.get("style", "Unknown")
        style_counts[style] = style_counts.get(style, 0) + 1

        # Materials
        for mat in analysis.get("materials", []):
            material_counts[mat] = material_counts.get(mat, 0) + 1

        # Colors
        for col in analysis.get("colors", []):
            color_counts[col] = color_counts.get(col, 0) + 1

        # Lighting
        lighting = analysis.get("lighting", "Unknown")
        lighting_counts[lighting] = lighting_counts.get(lighting, 0) + 1

        # Mood
        mood = analysis.get("mood", "Unknown")
        mood_counts[mood] = mood_counts.get(mood, 0) + 1

        # Architecture type
        arch_type = analysis.get("architecture_type", "Unknown")
        arch_type_counts[arch_type] = arch_type_counts.get(arch_type, 0) + 1

        # Environment
        env = analysis.get("environment", "Unknown")
        environment_counts[env] = environment_counts.get(env, 0) + 1

        # Key features
        for feat in analysis.get("key_features", []):
            key_features_counts[feat] = key_features_counts.get(feat, 0) + 1

    # Sap xep theo tan suat
    def top_items(counter: dict, n: int = 10) -> list:
        return sorted(counter.items(), key=lambda x: -x[1])[:n]

    style_guide = {
        "total_images_analyzed": total_valid,
        "folders_analyzed": TRAIN_DIRS,
        "style_distribution": top_items(style_counts),
        "dominant_style": max(style_counts, key=style_counts.get) if style_counts else "Unknown",
        "materials": top_items(material_counts),
        "top_materials": [m for m, c in top_items(material_counts, 5)],
        "colors": top_items(color_counts),
        "primary_palette": [c for c, _ in top_items(color_counts, 6)],
        "lighting_conditions": top_items(lighting_counts),
        "dominant_lighting": max(lighting_counts, key=lighting_counts.get) if lighting_counts else "Unknown",
        "mood_distribution": top_items(mood_counts),
        "dominant_mood": max(mood_counts, key=mood_counts.get) if mood_counts else "Unknown",
        "architecture_types": top_items(arch_type_counts),
        "environments": top_items(environment_counts),
        "key_features": top_items(key_features_counts, 15),
        "top_key_features": [f for f, c in top_items(key_features_counts, 8)],
    }

    # Luu Style Guide
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        json.dump(style_guide, f, ensure_ascii=False, indent=2)
    print(f"[OK] Da luu Style Guide vao: {SUMMARY_FILE}")

    # In bao cao
    print(f"\n{'='*60}")
    print(f"BAO CAO PHAN TICH STYLE ({total_valid} anh)")
    print(f"{'='*60}")

    print(f"\nPHONG CACH KIEN TRUC (Top 5):")
    for style, count in top_items(style_counts, 5):
        pct = count / total_valid * 100
        print(f"   {style}: {count} anh ({pct:.1f}%)")

    print(f"\nBANG MAU CHU DAO (Top 6):")
    for color, count in top_items(color_counts, 6):
        pct = count / total_valid * 100
        print(f"   {color}: {count} anh ({pct:.1f}%)")

    print(f"\nVAT LIEU (Top 5):")
    for mat, count in top_items(material_counts, 5):
        pct = count / total_valid * 100
        print(f"   {mat}: {count} anh ({pct:.1f}%)")

    print(f"\nANH SANG (Top 3):")
    for light, count in top_items(lighting_counts, 3):
        pct = count / total_valid * 100
        print(f"   {light}: {count} anh ({pct:.1f}%)")

    print(f"\nTAM TRANG (Top 3):")
    for mood, count in top_items(mood_counts, 3):
        pct = count / total_valid * 100
        print(f"   {mood}: {count} anh ({pct:.1f}%)")

    print(f"\nLOAI CONG TRINH:")
    for arch, count in top_items(arch_type_counts):
        pct = count / total_valid * 100
        print(f"   {arch}: {count} anh ({pct:.1f}%)")

    print(f"\nMOI TRUONG XUNG QUANH:")
    for env, count in top_items(environment_counts):
        pct = count / total_valid * 100
        print(f"   {env}: {count} anh ({pct:.1f}%)")

    print(f"\nCHI TIET KIEN TRUC NOI BAT (Top 8):")
    for feat, count in top_items(key_features_counts, 8):
        pct = count / total_valid * 100
        print(f"   {feat}: {count} anh ({pct:.1f}%)")

    print(f"\n{'='*60}")
    return style_guide


def generate_system_prompt(style_guide: dict) -> str:
    """Tao System Prompt cho PromptWriter dua tren Style Guide da hoc."""

    # Tong hop mo ta style chinh
    styles_desc = ", ".join([s for s, _ in style_guide.get("style_distribution", [])[:4]])
    materials_desc = ", ".join(style_guide.get("top_materials", []))
    colors_desc = ", ".join(style_guide.get("primary_palette", []))
    lighting_desc = style_guide.get("dominant_lighting", "natural daylight")
    mood_desc = style_guide.get("dominant_mood", "modern")
    features_desc = ", ".join(style_guide.get("top_key_features", []))

    system_prompt = f"""You are an expert architectural photographer and AI art director. You have been trained on a curated dataset of {style_guide['total_images_analyzed']} architectural images.

## YOUR TRAINED STYLE PROFILE

### Dominant Architectural Styles
The user's preferred styles are: {styles_desc}.
Always favor these styles when generating prompts. If the user requests a different style, blend it with these preferences.

### Preferred Materials
The user's typical materials include: {materials_desc}.
Incorporate these materials naturally in every generation.

### Color Palette
The user's signature color palette centers around: {colors_desc}.
Ensure color harmony follows this palette as the foundation.

### Lighting Preferences
The user prefers: {lighting_desc} lighting conditions.
Use this as the default lighting setup, adjusting only when the user specifies otherwise.

### Emotional Tone
The target mood is: {mood_desc}.
All generations should evoke this emotional quality.

### Architectural Details
Key features to emphasize: {features_desc}.
These details should be visible and prominent in every generation.

## GENERATION RULES

### Image Prompt Structure (200 words max)
1. Start with the architectural style and type
2. Describe materials and colors
3. Specify lighting conditions and time of day
4. Add camera angle (eye-level / low angle / aerial / worm's-eye view)
5. Describe the atmosphere and mood
6. Include environmental context
7. End with quality tags: ultra realistic, architectural photography, 8k, award winning, professional

### Video Prompt Structure (100 words max)
1. Start with camera movement (slow push-in / gentle orbit / dolly forward / pan)
2. Describe the scene and its atmosphere
3. Include time of day and lighting
4. Mention duration and cinematic quality
5. End with: cinematic, 4k, smooth motion, professional grade

### Negative Prompt
Always include: distorted, low quality, blurry, unnatural colors, cartoonish, oversaturated, warped perspective, asymmetric, cluttered, chaotic

### Output Format
Always respond in JSON with these exact keys:
{{"image_prompt", "video_prompt", "negative_prompt", "style_tags"}}

## IMPORTANT CONSTRAINTS
- NEVER use generic prompts. Every prompt must feel specific and intentional.
- ALWAYS reference the trained style profile above as the default aesthetic
- When the user provides a reference image, blend its style with the trained profile
- PREVENT style drift: always anchor back to {styles_desc} aesthetic
- FOCUS on high-end, luxury, award-winning architectural quality
"""
    return system_prompt


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train AI - Architecture Style Analyzer")
    parser.add_argument("--sample", type=int, default=0,
                        help="Chi phan tich N anh mau (mac dinh: 0 = tat ca)")
    parser.add_argument("--mock", action="store_true",
                        help="Chay mock khong goi API that (dung de test)")
    args = parser.parse_args()

    print("=" * 60)
    print("[TRAIN AI] ARCHITECTURE STYLE ANALYZER")
    print("=" * 60)
    print()

    if args.mock:
        print("[MOCK MODE] Chay voi du lieu gia lap...\n")
        mock_results = {}
        mock_styles = [
            "Modern Minimalist", "Contemporary", "Industrial",
            "Mid-Century Modern", "Tropical Modern", "Brutalist",
            "Neoclassical", "Scandinavian", "Japanese Minimalist", "Art Deco"
        ]
        mock_materials_pool = [
            ["concrete", "glass", "steel"],
            ["wood", "glass", "stone"],
            ["white plaster", "glass", "wood"],
            ["brick", "steel", "glass"],
            ["stone", "glass", "concrete"],
            ["wood", "bamboo", "glass"],
            ["marble", "glass", "steel"],
        ]
        mock_colors_pool = [
            ["#FFFFFF", "#C0C0C0", "#404040"],
            ["#F5F5DC", "#8B7355", "#2F4F4F"],
            ["#FFFAF0", "#DEB887", "#2F2F2F"],
            ["#F0F0F0", "#A9A9A9", "#1A1A1A"],
            ["#E8DCC8", "#556B2F", "#8B4513"],
            ["#FDF5E6", "#BDB76B", "#696969"],
        ]
        mock_lighting = [
            "natural golden hour", "soft diffused daylight",
            "dramatic shadows", "warm evening", "bright overcast",
            "natural morning light", "cool blue hour"
        ]
        mock_moods = [
            "peaceful", "luxurious", "serene", "dramatic",
            "elegant", "cozy", "futuristic", "minimal"
        ]
        mock_features = [
            "floor-to-ceiling windows", "open plan layout", "clean lines",
            "green roof", "outdoor terrace", "natural stone walls",
            "cantilever", "floating staircase", "pool integration",
            "wood paneling", "glass bridge", "skylight"
        ]

        import random
        random.seed(42)

        for dir_idx, dir_path in enumerate(TRAIN_DIRS):
            for i in range(20):
                img_path = os.path.join(dir_path, f"mock_image_{i+1}.png")
                mock_results[img_path] = {
                    "style": random.choice(mock_styles),
                    "materials": random.sample(random.choice(mock_materials_pool),
                                               k=min(random.randint(2, 4), len(random.choice(mock_materials_pool)))),
                    "colors": random.choice(mock_colors_pool),
                    "lighting": random.choice(mock_lighting),
                    "mood": random.choice(mock_moods),
                    "architecture_type": random.choice(["house", "villa", "commercial", "interior", "landscape"]),
                    "environment": random.choice(["urban", "suburban", "natural", "waterfront", "mountain"]),
                    "key_features": random.sample(mock_features, random.randint(3, 6)),
                    "similarity_to_trained": "high",
                }
        results = mock_results
        print(f"Da tao {len(results)} ket qua mock\n")
    else:
        results = analyze_all_images(args.sample)

    # Buoc 2: Tong hop Style Guide
    style_guide = compile_style_guide(results)

    # Buoc 3: Tao System Prompt
    system_prompt = generate_system_prompt(style_guide)
    prompt_file = OUTPUT_DIR / "trained_system_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(system_prompt)
    print(f"\n[OK] Da luu System Prompt vao: {prompt_file}")

    # Buoc 4: Xuat tat ca
    all_output = {
        "style_guide": style_guide,
        "system_prompt": system_prompt,
    }
    combined_file = OUTPUT_DIR / "trained_style_profile.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(all_output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Da luu Style Profile hoan chinh vao: {combined_file}")

    print(f"\n{'='*60}")
    print(f"[DONE] AI da hoc duoc style tu {len(results)} anh.")
    print(f"[INFO] Hay dung 'trained_style_profile.json' trong pipeline chinh.")
    print(f"[INFO] Hoac chay pipeline de tu dong su dung style da hoc.")


if __name__ == "__main__":
    main()
