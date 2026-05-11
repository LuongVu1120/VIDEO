"""
CLIP Style Matcher — Semantic similarity search using trained embeddings.

Replaces rule-based JSON lookup with real vector similarity:
- Takes a query image (base64)
- Generates CLIP embedding
- Queries ChromaDB for top-K visually similar training images
- Returns aggregated style profile weighted by similarity score

Falls back gracefully if CLIP deps not installed or training not done.
"""

import json
import io
import base64
from pathlib import Path
from collections import Counter
from typing import Optional

CHROMA_DIR = str(
    Path(__file__).parent.parent.parent / "scripts" / "training_output" / "chroma_db"
)
CLIP_PROFILE_PATH = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "training_output"
    / "clip_style_profile.json"
)

# Module-level singletons (loaded once, reused across requests)
_model = None
_processor = None
_device = None
_collection = None
_clip_profile: Optional[dict] = None


def is_clip_ready() -> bool:
    """True if CLIP training has been done and all deps are installed."""
    if not CLIP_PROFILE_PATH.exists():
        return False
    try:
        import torch
        import chromadb
        from transformers import CLIPModel, CLIPProcessor  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_clip_loaded() -> bool:
    """Lazy-load CLIP model (downloaded from HuggingFace on first run)."""
    global _model, _processor, _device
    if _model is not None:
        return True
    try:
        import torch
        import torch.nn.functional as F  # noqa: F401
        from transformers import CLIPModel, CLIPProcessor

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = "openai/clip-vit-base-patch32"
        _model = CLIPModel.from_pretrained(model_name).to(_device)
        _processor = CLIPProcessor.from_pretrained(model_name)
        _model.eval()
        return True
    except Exception as e:
        print(f"[CLIP] Load failed: {e}")
        return False


def _ensure_collection_loaded() -> bool:
    """Lazy-load ChromaDB collection."""
    global _collection
    if _collection is not None:
        return True
    try:
        import chromadb

        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_collection("arch_styles")
        count = _collection.count()
        print(f"[CLIP] ChromaDB loaded: {count} embeddings.")
        return True
    except Exception as e:
        print(f"[CLIP] ChromaDB load failed: {e}")
        return False


def _load_clip_profile() -> Optional[dict]:
    global _clip_profile
    if _clip_profile is not None:
        return _clip_profile
    if not CLIP_PROFILE_PATH.exists():
        return None
    try:
        with open(CLIP_PROFILE_PATH, "r", encoding="utf-8") as f:
            _clip_profile = json.load(f)
        return _clip_profile
    except Exception:
        return None


def get_similar_styles(image_base64: str, top_k: int = 12) -> dict:
    """
    Core function: find top_k training images most visually similar to the query.

    Returns dict with CLIP-powered style analysis:
    {
        "clip_dominant_style": "Contemporary",
        "clip_style_distribution": [["Contemporary", 0.72], ...],
        "clip_top_matches": [{"filename": "...", "style": "...", "similarity": 0.91}, ...],
        "clip_confidence": 0.85,
        "clip_total_trained": 83,
    }

    Returns {} if CLIP not available (pipeline falls back to color-based analysis).
    """
    if not is_clip_ready():
        return {}

    if not _ensure_clip_loaded() or not _ensure_collection_loaded():
        return {}

    import torch
    import torch.nn.functional as F

    # Decode image
    try:
        image_data = base64.b64decode(image_base64)
        from PIL import Image
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
    except Exception as e:
        print(f"[CLIP] Image decode error: {e}")
        return {}

    # Generate query embedding
    try:
        with torch.no_grad():
            inputs = _processor(images=image, return_tensors="pt").to(_device)
            image_feats = _model.get_image_features(**inputs)
            image_feats = F.normalize(image_feats, dim=-1)
            query_embedding = image_feats[0].cpu().numpy().tolist()
    except Exception as e:
        print(f"[CLIP] Embedding error: {e}")
        return {}

    # Query ChromaDB
    try:
        n = min(top_k, _collection.count())
        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            include=["metadatas", "distances"],
        )
    except Exception as e:
        print(f"[CLIP] ChromaDB query error: {e}")
        return {}

    if not results or not results.get("metadatas"):
        return {}

    matches = results["metadatas"][0]
    distances = results["distances"][0]  # cosine distance: lower = more similar

    # Weighted style aggregation (similarity = 1 - cosine_distance)
    style_weights: Counter = Counter()
    for meta, dist in zip(matches, distances):
        similarity = max(0.0, 1.0 - float(dist))
        style = meta.get("style", "Contemporary")
        style_weights[style] += similarity

    total_weight = sum(style_weights.values())
    if total_weight == 0:
        return {}

    dominant_style = style_weights.most_common(1)[0][0]
    style_distribution = [
        [s, round(w / total_weight, 3)]
        for s, w in style_weights.most_common(5)
    ]
    confidence = round(style_weights[dominant_style] / total_weight, 3)

    profile = _load_clip_profile()

    return {
        "clip_dominant_style": dominant_style,
        "clip_style_distribution": style_distribution,
        "clip_top_matches": [
            {
                "filename": m.get("filename", ""),
                "style": m.get("style", ""),
                "similarity": round(1.0 - float(d), 3),
            }
            for m, d in zip(matches[:5], distances[:5])
        ],
        "clip_confidence": confidence,
        "clip_total_trained": profile.get("total_images", 0) if profile else 0,
    }


def enrich_style_analysis(style_analysis: dict, image_base64: str) -> dict:
    """
    Enrich an existing style_analysis dict with CLIP similarity data.
    If CLIP is available, overrides 'style' with the CLIP-predicted dominant style
    when confidence is high enough (>0.6).
    Always safe to call — returns original dict unchanged if CLIP unavailable.
    """
    clip_data = get_similar_styles(image_base64)
    if not clip_data:
        return style_analysis

    enriched = dict(style_analysis)
    enriched["clip_analysis"] = clip_data

    # Override style only if CLIP is confident
    if clip_data.get("clip_confidence", 0) >= 0.55:
        clip_style = clip_data["clip_dominant_style"]
        enriched["style"] = clip_style
        enriched["style_source"] = "clip_embedding"
        print(
            f"[CLIP] Style override: {style_analysis.get('style')} → {clip_style} "
            f"(confidence={clip_data['clip_confidence']:.0%})"
        )
    else:
        enriched["style_source"] = "vision_model"

    return enriched
