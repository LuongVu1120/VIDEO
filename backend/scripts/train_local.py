"""
Train Analyzer OFFLINE — Khong can API key.
Su dung CLIP model (mien phi) + Color Analysis de phan tich style.

Cai dat: pip install transformers torch pillow scikit-learn
"""

import sys
import os
import json
import base64
from pathlib import Path
from collections import Counter
from PIL import Image
import io

# Them backend vao sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Architecture style labels for CLIP zero-shot classification
ARCHITECTURE_STYLES = [
    "Contemporary architecture",
    "Modern Minimalist architecture",
    "Neoclassical architecture",
    "Mediterranean architecture",
    "Industrial architecture",
    "Brutalist architecture",
    "Tropical architecture",
    "Scandinavian architecture",
    "Japanese Zen architecture",
    "Spanish Revival architecture",
    "Modern Farmhouse architecture",
    "Art Deco architecture",
    "Victorian architecture",
    "Glass and steel skyscraper",
    "Concrete modernist building",
]

MATERIALS = [
    "glass facade building",
    "wooden structure architecture",
    "stone masonry building",
    "steel frame architecture",
    "concrete building",
    "brick architecture",
    "marble surface building",
    "metal panel facade",
    "stucco exterior",
    "terracotta tiles",
    "green roof vegetation",
    "corten steel weathering",
]

LIGHTING_CONDITIONS = [
    "golden hour warm sunset lighting",
    "bright midday sunlight",
    "soft overcast diffused lighting",
    "blue hour twilight lighting",
    "dramatic shadow contrast lighting",
    "night artificial lighting",
    "rainy moody lighting",
    "foggy atmospheric lighting",
]

ENVIRONMENTS = [
    "urban cityscape background",
    "suburban neighborhood setting",
    "natural forest landscape",
    "waterfront coastal setting",
    "mountain backdrop",
    "desert landscape",
    "tropical garden setting",
    "minimalist zen garden",
]

MOODS = [
    "peaceful serene atmosphere",
    "dramatic bold atmosphere",
    "luxurious elegant atmosphere",
    "cozy warm atmosphere",
    "futuristic innovative atmosphere",
    "minimalist clean atmosphere",
    "rustic natural atmosphere",
    "industrial raw atmosphere",
]

# ======================== PATHS ========================

TRAIN_DIRS = [
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "1"),
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "2"),
]

OUTPUT_DIR = Path(__file__).parent / "training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESULT_FILE = OUTPUT_DIR / "analysis_results.json"
SUMMARY_FILE = OUTPUT_DIR / "style_summary.json"
PROFILE_FILE = OUTPUT_DIR / "trained_style_profile.json"
PROMPT_FILE = OUTPUT_DIR / "trained_system_prompt.txt"


def get_image_files(directory: str) -> list[str]:
    """Lay tat ca file anh, bo qua AI-enhanced."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
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
        print(f"  [FILTER] Bo qua {skipped} anh AI-enhanced")
    return sorted(files)


def load_clip_model():
    """Load CLIP model for zero-shot classification."""
    try:
        from transformers import CLIPProcessor, CLIPModel
        import torch
        
        model_name = "openai/clip-vit-base-patch32"
        print(f"[CLIP] Loading {model_name}...")
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        print(f"[CLIP] Model loaded on {device}")
        return model, processor, device
    except ImportError:
        print("[ERROR] transformers/torch not installed. Run: pip install transformers torch")
        return None, None, None


def classify_with_clip(model, processor, device, image: Image.Image, labels: list[str]) -> list[tuple[str, float]]:
    """Zero-shot classification using CLIP."""
    import torch
    
    inputs = processor(
        text=labels,
        images=image,
        return_tensors="pt",
        padding=True,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits_per_image = outputs.logits_per_image
        probs = logits_per_image.softmax(dim=1)
    
    results = [(labels[i], float(probs[0][i])) for i in range(len(labels))]
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def analyze_colors(image: Image.Image) -> dict:
    """Extract dominant color palette using color quantization."""
    import numpy as np
    from sklearn.cluster import KMeans
    
    # Resize for faster processing
    img = image.resize((200, 200))
    pixels = np.array(img).reshape(-1, 3)
    
    # K-means clustering to find dominant colors
    k = 8
    kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
    kmeans.fit(pixels)
    
    colors = kmeans.cluster_centers_.astype(int)
    labels_counts = Counter(kmeans.labels_)
    
    # Sort by frequency
    color_data = []
    for i, count in labels_counts.most_common():
        r, g, b = colors[i]
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        percentage = count / len(kmeans.labels_)
        color_data.append({"hex": hex_code, "rgb": [r, g, b], "pct": round(percentage, 3)})
    
    return {
        "dominant_colors": color_data[:5],
        "is_warm_dominant": sum(c["rgb"][0] > c["rgb"][2] for c in color_data[:3]) >= 2,
        "is_cool_dominant": sum(c["rgb"][2] > c["rgb"][0] for c in color_data[:3]) >= 2,
    }


def analyze_brightness(image: Image.Image) -> dict:
    """Analyze overall brightness and contrast."""
    import numpy as np
    
    gray = image.convert("L")
    pixels = np.array(gray)
    mean_brightness = float(pixels.mean())
    std_contrast = float(pixels.std())
    
    # Classify lighting based on brightness
    if mean_brightness > 170:
        lighting_type = "bright"
    elif mean_brightness > 120:
        lighting_type = "moderate"
    elif mean_brightness > 70:
        lighting_type = "dim"
    else:
        lighting_type = "dark"
    
    return {
        "mean_brightness": round(mean_brightness, 1),
        "contrast": round(std_contrast, 1),
        "lighting_type": lighting_type,
    }


def analyze_one_image(image_path: str, model, processor, device) -> dict:
    """Analyze one image using CLIP + color analysis."""
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"  [ERROR] Cannot open {image_path}: {e}")
        return None
    
    result = {}
    
    # CLIP classification for styles
    if model and processor:
        style_scores = classify_with_clip(model, processor, device, image, ARCHITECTURE_STYLES)
        result["style"] = style_scores[0][0].replace(" architecture", "")
        result["style_scores"] = {s.replace(" architecture", ""): round(v, 3) for s, v in style_scores[:5]}
        
        material_scores = classify_with_clip(model, processor, device, image, MATERIALS)
        result["materials"] = [m.replace(" architecture", "").replace(" building", "") for m, _ in material_scores[:4]]
        result["material_scores"] = {m.replace(" architecture", "").replace(" building", ""): round(v, 3) for m, v in material_scores[:4]}
        
        lighting_scores = classify_with_clip(model, processor, device, image, LIGHTING_CONDITIONS)
        result["lighting"] = lighting_scores[0][0].replace(" lighting", "")
        
        env_scores = classify_with_clip(model, processor, device, image, ENVIRONMENTS)
        result["environment"] = env_scores[0][0].replace(" background", "").replace(" setting", "").replace(" landscape", "")
        
        mood_scores = classify_with_clip(model, processor, device, image, MOODS)
        result["mood"] = mood_scores[0][0].replace(" atmosphere", "")
    else:
        result["style"] = "Contemporary"
        result["materials"] = ["glass", "concrete", "steel"]
        result["lighting"] = "natural"
        result["environment"] = "urban"
        result["mood"] = "modern"
    
    # Color analysis
    color_data = analyze_colors(image)
    result["colors"] = [c["hex"] for c in color_data["dominant_colors"]]
    result["color_details"] = color_data
    
    # Brightness analysis
    brightness = analyze_brightness(image)
    result["brightness"] = brightness
    
    # Image dimensions
    result["dimensions"] = f"{image.width}x{image.height}"
    
    return result


def summarize_results(all_results: dict) -> dict:
    """Create style summary from all analyzed images."""
    styles = Counter()
    materials = Counter()
    colors = Counter()
    lightings = Counter()
    moods = Counter()
    environments = Counter()
    
    for path, analysis in all_results.items():
        if not analysis:
            continue
        styles[analysis.get("style", "Unknown")] += 1
        moods[analysis.get("mood", "Unknown")] += 1
        lightings[analysis.get("lighting", "Unknown")] += 1
        environments[analysis.get("environment", "Unknown")] += 1
        for m in analysis.get("materials", []):
            materials[m] += 1
        for c in analysis.get("colors", []):
            colors[c] += 1
    
    total = len(all_results)
    
    return {
        "total_images_analyzed": total,
        "style_distribution": styles.most_common(10),
        "dominant_style": styles.most_common(1)[0][0] if styles else "Unknown",
        "materials": materials.most_common(15),
        "top_materials": [m for m, _ in materials.most_common(5)],
        "colors": colors.most_common(15),
        "primary_palette": [c for c, _ in colors.most_common(5)],
        "lighting_distribution": lightings.most_common(5),
        "dominant_lighting": lightings.most_common(1)[0][0] if lightings else "Unknown",
        "mood_distribution": moods.most_common(5),
        "dominant_mood": moods.most_common(1)[0][0] if moods else "Unknown",
        "environment_distribution": environments.most_common(5),
        "dominant_environment": environments.most_common(1)[0][0] if environments else "Unknown",
    }


def generate_system_prompt(style_guide: dict) -> str:
    """Generate system prompt from style guide."""
    styles = [s for s, _ in style_guide.get("style_distribution", [])[:3]]
    materials = style_guide.get("top_materials", [])
    colors = style_guide.get("primary_palette", [])
    lighting = style_guide.get("dominant_lighting", "natural")
    mood = style_guide.get("dominant_mood", "peaceful")
    environments = [e for e, _ in style_guide.get("environment_distribution", [])[:3]]
    
    return f"""You are an expert architectural photographer and AI art director. 
You have been trained on a curated dataset of {style_guide.get('total_images_analyzed', 0)} architectural images.

## TRAINED STYLE PROFILE

### Dominant Architectural Styles
The user's preferred styles are: {', '.join(styles)}.
Always favor these styles when generating prompts.

### Preferred Materials
The user's typical materials include: {', '.join(materials)}.
Incorporate these materials naturally in every generation.

### Color Palette
The user's signature color palette centers around: {', '.join(colors)}.
Ensure color harmony follows this palette as the foundation.

### Lighting Preferences
The user prefers: {lighting} lighting conditions.
Use this as the default lighting setup.

### Emotional Tone
The target mood is: {mood}.
All generations should evoke this emotional quality.

### Environment Context
Preferred settings: {', '.join(environments)}.

## PROMPT GENERATION RULES

### Image Prompt Structure
1. Start with architectural style and type
2. Describe materials and colors
3. Specify lighting conditions and time of day
4. Add camera angle (eye-level / low angle / aerial)
5. Describe atmosphere and mood
6. Include environmental context
7. End with: ultra realistic, architectural photography, 8k, professional

### Negative Prompt
Always include: distorted, low quality, blurry, unnatural colors, cartoonish, oversaturated, warped perspective

### Output Format
Always respond in JSON with keys: image_prompt, video_prompt, negative_prompt, style_tags
"""


def main():
    print("=" * 60)
    print("TRAIN ANALYZER — OFFLINE (CLIP + Color Analysis)")
    print("=" * 60)
    
    # Load CLIP model
    model, processor, device = load_clip_model()
    
    # Collect images
    all_images = []
    for dir_path in TRAIN_DIRS:
        if os.path.exists(dir_path):
            images = get_image_files(dir_path)
            all_images.extend(images)
            print(f"[{dir_path}] Tim thay {len(images)} anh")
        else:
            print(f"[WARN] Thu muc khong ton tai: {dir_path}")
    
    print(f"\n=== Tong cong: {len(all_images)} anh can phan tich ===\n")
    
    # Load existing results
    existing_results = {}
    if RESULT_FILE.exists():
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
        print(f"Da load {len(existing_results)} ket qua tu file cu")
    
    # Analyze each image
    for i, img_path in enumerate(all_images):
        if img_path in existing_results and existing_results[img_path] is not None:
            continue
        
        img_name = os.path.basename(img_path)
        print(f"[{i+1}/{len(all_images)}] {img_name[:60]}...", end=" ", flush=True)
        
        analysis = analyze_one_image(img_path, model, processor, device)
        if analysis:
            existing_results[img_path] = analysis
            print(f"✓ {analysis.get('style', '?')}")
        else:
            print("✗ FAILED")
        
        # Save progress every 10 images
        if (i + 1) % 10 == 0:
            with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_results, f, indent=2, ensure_ascii=False)
            print(f"  [SAVE] Progress saved ({len(existing_results)} results)")
    
    # Final save
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_results, f, indent=2, ensure_ascii=False)
    
    # Generate summary
    print(f"\n=== Tao style summary tu {len(existing_results)} anh ===")
    style_guide = summarize_results(existing_results)
    
    style_profile = {"style_guide": style_guide}
    with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(style_profile, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] Style profile: {PROFILE_FILE}")
    
    # Generate system prompt
    system_prompt = generate_system_prompt(style_guide)
    with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
        f.write(system_prompt)
    print(f"[SAVE] System prompt: {PROMPT_FILE}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE!")
    print(f"Total images analyzed: {style_guide['total_images_analyzed']}")
    print(f"Dominant style: {style_guide['dominant_style']}")
    print(f"Top materials: {', '.join(style_guide['top_materials'])}")
    print(f"Color palette: {', '.join(style_guide['primary_palette'])}")
    print(f"Dominant mood: {style_guide['dominant_mood']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
