"""
Train CLIP — Real semantic AI embedding training.
Replaces train_fast.py (pixel counting) with CLIP 512-dim vectors stored in ChromaDB.
AI thực sự hiểu nội dung ảnh: style, materials, mood — không chỉ đếm màu.

Requirements: pip install transformers chromadb torch torchvision
Chay: python backend/scripts/train_clip.py
"""

import sys
import os
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

# ======================== PATHS ========================
TRAIN_DIRS = [
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "1"),
    str(Path(__file__).parent.parent.parent / "TRAIN AI" / "2"),
]
OUTPUT_DIR = Path(__file__).parent / "training_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHROMA_DIR = str(OUTPUT_DIR / "chroma_db")
CLIP_PROFILE_FILE = OUTPUT_DIR / "clip_style_profile.json"

STYLE_KEYWORDS = {
    "Contemporary": ["contemporary", "modern", "hien dai"],
    "Modern Minimalist": ["minimalist", "minimal", "toi gian", "don gian"],
    "Neoclassical": ["neoclassical", "classical", "co dien", "tan co dien"],
    "Mediterranean": ["mediterranean", "spanish", "italian"],
    "Industrial": ["industrial", "loft", "cong nghiep"],
    "Tropical": ["tropical", "resort", "nhiet doi", "balinese"],
    "Scandinavian": ["scandinavian", "nordic", "bac au"],
    "Japanese Zen": ["japanese", "zen", "nhat"],
    "Brutalist": ["brutalist", "brutalism", "concrete"],
    "Modern Farmhouse": ["farmhouse", "rustic", "nong thon"],
}

# CLIP text queries dùng để phân loại style (zero-shot classification)
STYLE_TEXT_QUERIES = {
    "Contemporary": "a contemporary modern house with clean lines and glass",
    "Modern Minimalist": "a minimalist house with simple geometric forms and neutral colors",
    "Neoclassical": "a neoclassical house with columns and ornate classical details",
    "Mediterranean": "a mediterranean villa with terracotta roof and warm stucco walls",
    "Industrial": "an industrial loft building with exposed concrete and steel beams",
    "Tropical": "a tropical resort villa with natural materials and open-air design",
    "Scandinavian": "a scandinavian nordic house with white walls and natural wood",
    "Japanese Zen": "a japanese zen house with minimalist garden and natural materials",
    "Brutalist": "a brutalist concrete building with raw geometric forms",
    "Modern Farmhouse": "a modern farmhouse with rustic wood and white shiplap",
}

SKIP_KEYWORDS = ['beautyplus', 'picsart', 'aiimageenhancer', 'enhancer']
VALID_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def get_image_files(directory: str) -> list[str]:
    if not os.path.exists(directory):
        return []
    files = []
    skipped = 0
    for f in os.listdir(directory):
        if os.path.splitext(f)[1].lower() not in VALID_EXTS:
            continue
        if any(kw in f.lower() for kw in SKIP_KEYWORDS):
            skipped += 1
            continue
        files.append(os.path.join(directory, f))
    if skipped:
        print(f"  [FILTER] Skipped {skipped} AI-enhanced images in {directory}")
    return sorted(files)


def keyword_guess_style(filepath: str) -> str:
    fp = filepath.lower()
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in fp for kw in keywords):
            return style
    return "Contemporary"


def clip_classify_style(image_features, text_features_map: dict, style_names: list) -> str:
    """Zero-shot CLIP classification: compare image embedding to style text embeddings."""
    import torch
    import torch.nn.functional as F

    best_style = "Contemporary"
    best_score = -1.0

    for style in style_names:
        text_feat = text_features_map[style]
        score = F.cosine_similarity(image_features, text_feat, dim=-1).item()
        if score > best_score:
            best_score = score
            best_style = style

    return best_style


def main():
    print("=" * 60)
    print("TRAIN CLIP — Semantic Embedding Training (Real AI)")
    print("=" * 60)

    # Import heavy deps
    try:
        import torch
        import torch.nn.functional as F
        from transformers import CLIPProcessor, CLIPModel
        from PIL import Image
        import chromadb
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("Install: pip install transformers chromadb torch torchvision pillow")
        sys.exit(1)

    # Device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n[CLIP] Device: {device}")

    # Load model
    model_name = "openai/clip-vit-base-patch32"
    print(f"[CLIP] Loading {model_name}...")
    model = CLIPModel.from_pretrained(model_name).to(device)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()
    print("[CLIP] Model loaded. (512-dim embeddings)")

    # Pre-compute text embeddings for zero-shot style classification
    style_names = list(STYLE_TEXT_QUERIES.keys())
    print("\n[CLIP] Pre-computing style text embeddings...")
    text_features_map = {}
    with torch.no_grad():
        for style, query in STYLE_TEXT_QUERIES.items():
            inputs = processor(text=[query], return_tensors="pt", padding=True).to(device)
            feats = model.get_text_features(**inputs)
            feats = F.normalize(feats, dim=-1)
            text_features_map[style] = feats
    print(f"[CLIP] {len(text_features_map)} style embeddings ready.")

    # Init ChromaDB
    print(f"\n[ChromaDB] Initializing at {CHROMA_DIR}")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        chroma_client.delete_collection("arch_styles")
        print("[ChromaDB] Deleted existing collection (retrain).")
    except Exception:
        pass
    collection = chroma_client.create_collection(
        "arch_styles",
        metadata={"hnsw:space": "cosine"},
    )

    # Gather images
    all_images = []
    for train_dir in TRAIN_DIRS:
        files = get_image_files(train_dir)
        if files:
            print(f"\n[DIR] {train_dir}: {len(files)} images")
        else:
            print(f"[WARN] Not found or empty: {train_dir}")
        all_images.extend(files)

    if not all_images:
        print("\n[ERROR] No training images found. Check TRAIN AI/ folders.")
        sys.exit(1)

    print(f"\n[TRAIN] Processing {len(all_images)} images...")

    ids, embeddings, metadatas = [], [], []
    style_counts = Counter()
    clip_classified = 0
    keyword_fallback = 0

    for i, img_path in enumerate(all_images):
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"  [SKIP] {os.path.basename(img_path)}: {e}")
            continue

        # Generate CLIP image embedding
        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt").to(device)
            image_feats = model.get_image_features(**inputs)
            image_feats_norm = F.normalize(image_feats, dim=-1)
            embedding = image_feats_norm[0].cpu().numpy().tolist()

        # Zero-shot CLIP style classification
        clip_style = clip_classify_style(image_feats_norm[0:1], text_features_map, style_names)
        keyword_style = keyword_guess_style(img_path)

        # Prefer CLIP classification; use keyword as secondary label
        final_style = clip_style
        clip_classified += 1

        style_counts[final_style] += 1
        img_id = f"img_{i:04d}"

        ids.append(img_id)
        embeddings.append(embedding)
        metadatas.append({
            "path": img_path,
            "filename": os.path.basename(img_path),
            "style": final_style,
            "keyword_style": keyword_style,
            "folder": os.path.basename(os.path.dirname(img_path)),
        })

        print(f"  [{i+1}/{len(all_images)}] {os.path.basename(img_path)[:45]:<45} CLIP={final_style}")

    if not ids:
        print("[ERROR] No images could be processed.")
        sys.exit(1)

    # Store in ChromaDB (batch to avoid memory spikes)
    BATCH = 50
    print(f"\n[ChromaDB] Storing {len(ids)} embeddings in batches of {BATCH}...")
    for start in range(0, len(ids), BATCH):
        end = min(start + BATCH, len(ids))
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )
    print(f"[ChromaDB] Done. Collection size: {collection.count()}")

    # Save summary profile
    dominant_style = style_counts.most_common(1)[0][0] if style_counts else "Contemporary"
    profile = {
        "total_images": len(ids),
        "dominant_style": dominant_style,
        "style_distribution": style_counts.most_common(),
        "chroma_db_path": CHROMA_DIR,
        "collection_name": "arch_styles",
        "embedding_dim": 512,
        "model": model_name,
        "classification_method": "clip_zero_shot",
        "clip_classified": clip_classified,
    }

    with open(CLIP_PROFILE_FILE, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVE] {CLIP_PROFILE_FILE}")
    print("\n" + "=" * 60)
    print("CLIP TRAINING COMPLETE!")
    print(f"  Images trained  : {len(ids)}")
    print(f"  Dominant style  : {dominant_style}")
    print(f"  Style breakdown : {dict(style_counts.most_common(5))}")
    print(f"  Vector DB       : {CHROMA_DIR}")
    print(f"  Embedding dims  : 512")
    print("\nNext step: the pipeline will automatically use CLIP embeddings")
    print("for style matching when you run the backend.")
    print("=" * 60)


if __name__ == "__main__":
    main()
