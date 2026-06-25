"""
Prompt sáng tạo mặc định cho video kiến trúc khi người dùng không nhập mô tả.

Mỗi variation nhận một kịch bản camera / ánh sáng / không gian khác nhau
(phù hợp Reels, TikTok, Shorts kiến trúc 2024–2026).
"""

from __future__ import annotations

import random
from typing import Any

from ..core.config import settings

# label_vi: hiển thị UI | prompt_vi / prompt_en: đưa vào pipeline AI
DEFAULT_VIDEO_DIRECTIONS: list[dict[str, str]] = [
    {
        "key": "day_to_night",
        "label_vi": "Ngày → đêm — đèn bật dần",
        "prompt_vi": (
            "Video kiến trúc chuyển từ ban ngày sang hoàng hôn rồi ban đêm: ánh nắng vàng dần tắt, "
            "bầu trời blue hour, đèn nội thất và đèn ngoài bật từng bước, slow dolly về mặt tiền công trình."
        ),
        "prompt_en": (
            "Cinematic architectural timelapse on one continuous shot: bright midday softens to golden hour, "
            "then blue hour twilight, interior and facade lights gradually turn on, slow motivated dolly "
            "push-in toward the building with realistic parallax and stable geometry."
        ),
        "tags": ["dramatic", "luxurious", "night", "evening"],
    },
    {
        "key": "night_to_day",
        "label_vi": "Đêm → sáng — bình minh ló dần",
        "prompt_vi": (
            "Từ cảnh đêm tĩnh lặng, bình minh ló dần: sương mù tan, ánh sáng leo lên mái và cửa kính, "
            "camera crane nhẹ từ thấp lên cao reveal toàn cảnh công trình."
        ),
        "prompt_en": (
            "Night exterior slowly transitions to sunrise: pre-dawn darkness lifts, warm sun kisses roof "
            "edges and glass facades, gentle crane rise from ground-level detail to full building reveal, "
            "smooth 24fps architectural documentary style."
        ),
        "tags": ["peaceful", "serene", "morning", "dawn"],
    },
    {
        "key": "seasons_spring_summer",
        "label_vi": "Chuyển mùa xuân → hè",
        "prompt_vi": (
            "Cây cối và vườn chuyển từ xuân sang hè: lá non đậm màu hơn, ánh sáng ấm hơn, "
            "camera orbit yavaş quanh công trình, nhấn mối liên kết kiến trúc với cảnh quan."
        ),
        "prompt_en": (
            "Subtle seasonal transition spring to summer around the architecture: fresh greenery becomes "
            "lush and saturated, warmer sunlight, slow 180-degree orbit around the structure showing "
            "landscape- architecture harmony, cinematic stabilized motion."
        ),
        "tags": ["peaceful", "natural", "garden", "tropical"],
    },
    {
        "key": "seasons_autumn_winter",
        "label_vi": "Thu → đông — lá vàng, sương mù",
        "prompt_vi": (
            "Chuyển từ thu sang đông: lá vàng rơi nhẹ, không khí lạnh hơn, sương mù buổi sáng, "
            "slow tracking shot dọc theo mặt tiền vật liệu gỗ và đá."
        ),
        "prompt_en": (
            "Autumn to early winter mood shift: golden leaves drift, cooler air, light morning fog, "
            "slow lateral tracking along facade highlighting wood stone and glass textures, "
            "photorealistic materials and soft diffused light."
        ),
        "tags": ["cozy", "serene", "forest", "mountain"],
    },
    {
        "key": "room_out_interior_to_exterior",
        "label_vi": "Room out — từ trong ra ngoài",
        "prompt_vi": (
            "Bắt đầu trong phòng khách / không gian nội thất hiện đại, camera đi về phía cửa kính lớn, "
            "cửa trượt mở dần ra sân hoặc hồ bơi và toàn cảnh ngoại thất — room-out reveal."
        ),
        "prompt_en": (
            "Room-out shot: start inside a refined living space, camera travels toward floor-to-ceiling "
            "glass, sliding doors open gradually revealing terrace pool and exterior architecture, "
            "seamless interior-to-exterior transition with depth and parallax."
        ),
        "tags": ["luxurious", "cozy", "interior", "pool"],
    },
    {
        "key": "room_in_exterior_to_interior",
        "label_vi": "Room in — từ ngoài vào trong",
        "prompt_vi": (
            "Tiếp cận từ lối vào ngoài trời, đi qua cửa chính vào foyer / phòng khách, "
            "ánh sáng tự nhiên đổ vào không gian nội thất — room-in walk-through kiến trúc."
        ),
        "prompt_en": (
            "Room-in architectural walk-through: approach from exterior entry path, pass through main "
            "door into foyer and living volume, natural daylight floods interior, continuous forward "
            "dolly with realistic spatial depth, no flat Ken Burns slide."
        ),
        "tags": ["modern", "contemporary", "minimalist"],
    },
    {
        "key": "drone_orbit_sunset",
        "label_vi": "Drone orbit — hoàng hôn",
        "prompt_vi": (
            "Góc máy như drone orbit 360° chậm quanh công trình lúc hoàng hôn, bầu trời cam hồng, "
            "phản chiếu trên kính và hồ nước nếu có."
        ),
        "prompt_en": (
            "Slow aerial-style orbit around the building at sunset, orange-pink sky gradients, "
            "reflections on glass and water surfaces, smooth circular camera path with 3D parallax, "
            "premium real-estate reel aesthetic."
        ),
        "tags": ["dramatic", "luxurious", "waterfront", "coastal"],
    },
    {
        "key": "hyperlapse_facade",
        "label_vi": "Hyperlapse dọc mặt tiền",
        "prompt_vi": (
            "Hyperlapse / tracking nhanh nhưng mượt dọc theo mặt tiền, nhấn chi tiết vật liệu và tỷ lệ, "
            "kết thúc bằng wide shot toàn cảnh."
        ),
        "prompt_en": (
            "Smooth architectural hyperlapse along the facade: accelerated lateral travel with "
            "stabilized motion, material details and proportions emphasized, ends on a wide hero "
            "establishing shot of the full structure."
        ),
        "tags": ["futuristic", "urban", "commercial"],
    },
    {
        "key": "material_macro_pullback",
        "label_vi": "Macro vật liệu → pullback",
        "prompt_vi": (
            "Cận cảnh chi tiết vật liệu (gỗ, bê tông, đá, kính) rồi camera lùi dần (pull back) "
            "để reveal toàn thể kiến trúc."
        ),
        "prompt_en": (
            "Start on macro detail of signature material — brushed concrete warm oak stone or glass — "
            "then slow pull-back reveal pulling away to show full architectural composition, "
            "shallow to deep focus transition, tactile realism."
        ),
        "tags": ["minimalist", "serene", "industrial"],
    },
    {
        "key": "rain_to_clear_glass",
        "label_vi": "Mưa → nắng trên kính",
        "prompt_vi": (
            "Giọt nước trên cửa kính / mái hiên, mưa nhẹ chuyển sang nắng, ánh sáng lóe qua vách kính, "
            "cảm giác sang trọng và thực tế."
        ),
        "prompt_en": (
            "Rain droplets on glass canopy or window, light rain easing to clear sky, sun breaks through "
            "illuminating glass facade with crisp reflections, moody to bright transition, "
            "slow push-in on glazing."
        ),
        "tags": ["luxurious", "dramatic", "modern"],
    },
    {
        "key": "pool_reflection",
        "label_vi": "Phản chiếu hồ bơi / mặt nước",
        "prompt_vi": (
            "Camera bắt đầu từ phản chiếu công trình trên mặt hồ bơi hoặc hồ nước, sóng nhẹ, "
            "rồi tilt up hoặc dolly lên bản thật kiến trúc."
        ),
        "prompt_en": (
            "Low angle on building reflection in still pool water, gentle ripples distort then clarify "
            "mirror image, camera tilts up or dollies to reveal real structure above water line, "
            "luxury villa resort reel style."
        ),
        "tags": ["luxurious", "tropical", "pool", "waterfront"],
    },
    {
        "key": "foliage_reveal",
        "label_vi": "Lộ diện qua cây xanh",
        "prompt_vi": (
            "Công trình ló dần từ sau lá cây / cành cây foreground, parallax tự nhiên, "
            "ánh sáng xuyên qua lá — phong cách resort / biệt thự xanh."
        ),
        "prompt_en": (
            "Architecture revealed through foreground foliage: leaves and branches frame the building, "
            "camera peeks through greenery with natural parallax, dappled sunlight, "
            "eco-luxury architectural storytelling."
        ),
        "tags": ["peaceful", "tropical", "garden", "natural"],
    },
    {
        "key": "twilight_interior_glow",
        "label_vi": "Ánh sáng nội thất ban đêm",
        "prompt_vi": (
            "Ngoại thất ban đêm, ánh sáng vàng ấm từ trong xuyên qua cửa kính, "
            "slow orbit hoặc dolly nhấn sự ấm áp của không gian sống."
        ),
        "prompt_en": (
            "Exterior at twilight, warm interior glow spills through large windows, slow orbit or "
            "dolly emphasizing inviting lit volumes inside, dark blue sky contrast, "
            "high-end residential marketing film."
        ),
        "tags": ["cozy", "luxurious", "night"],
    },
    {
        "key": "cloud_timelapse_sky",
        "label_vi": "Mây trôi — bầu trời động",
        "prompt_vi": (
            "Camera tĩnh hoặc rất chậm trên công trình, mây và ánh sáng thay đổi trên bầu trời, "
            "time-lapse feel trong một shot liên tục."
        ),
        "prompt_en": (
            "Mostly static or ultra-slow camera on building while clouds and light evolve across sky, "
            "subtle timelapse energy in a single continuous clip, emphasizes monumentality and "
            "time passing, clean architectural silhouette."
        ),
        "tags": ["serene", "minimalist", "peaceful"],
    },
    {
        "key": "terrace_lifestyle",
        "label_vi": "Sân thượng / terrace lifestyle",
        "prompt_vi": (
            "Không gian sân thượng, ban công hoặc terrace với view panorama, camera pan chậm "
            "từ không gian ngoài trời ra skyline hoặc cảnh quan."
        ),
        "prompt_en": (
            "Rooftop terrace or balcony lifestyle reveal: slow pan from outdoor seating and planters "
            "to panoramic view of landscape or city skyline beyond the architecture, "
            "aspirational outdoor living, golden hour warmth."
        ),
        "tags": ["luxurious", "urban", "cozy"],
    },
    {
        "key": "snow_melt_reveal",
        "label_vi": "Tuyết tan — reveal công trình",
        "prompt_vi": (
            "Cảnh có tuyết nhẹ hoặc sương giá dần tan, công trình hiện rõ hơn, "
            "ánh sáng lạnh chuyển ấm — phù hợp kiến trúc vùng lạnh hoặc mood cinematic."
        ),
        "prompt_en": (
            "Light snow or frost on landscape gradually melts, building emerges clearer as cold blue "
            "light warms slightly, subtle seasonal melt reveal, crisp winter architecture aesthetic "
            "transitioning to soft morning warmth."
        ),
        "tags": ["serene", "dramatic", "mountain"],
    },
]


def _score_direction(direction: dict[str, str], style_analysis: dict[str, Any] | None) -> int:
    if not style_analysis:
        return 0
    blob = " ".join(
        str(style_analysis.get(k, ""))
        for k in ("style", "mood", "lighting", "environment", "architecture_type", "time_of_day")
    ).lower()
    blob += " " + " ".join(style_analysis.get("materials", []) or [])
    blob += " " + " ".join(style_analysis.get("key_features", []) or [])
    score = 0
    for tag in direction.get("tags", []):
        if tag.lower() in blob:
            score += 2
    return score


def pick_default_direction(
    variation_index: int = 0,
    style_analysis: dict[str, Any] | None = None,
    *,
    seed: int | None = None,
) -> dict[str, str]:
    """
    Chọn một kịch bản video mặc định.
    Ưu tiên khớp mood/bối cảnh; xoay vòng theo variation_index để mỗi clip khác nhau.
    """
    pool = list(DEFAULT_VIDEO_DIRECTIONS)
    if seed is not None:
        rng = random.Random(seed)
        pool = pool.copy()
        rng.shuffle(pool)

    scored = sorted(
        pool,
        key=lambda d: (-_score_direction(d, style_analysis), pool.index(d)),
    )

    # Lấy top khớp nhất, xoay theo index để variation 0/1 khác nhau
    tier_score = _score_direction(scored[0], style_analysis)
    top_tier = [d for d in scored if _score_direction(d, style_analysis) == tier_score]
    return top_tier[variation_index % len(top_tier)]


def _build_prompt_text(direction: dict[str, str]) -> str:
    """Ghép prompt VI + EN cho model text (DeepSeek / GPT)."""
    vi = direction["prompt_vi"]
    en = direction["prompt_en"]
    lang = (settings.CONTENT_LANGUAGE or "vi").lower()
    if lang.startswith("en"):
        return en
    return f"{vi}\n\n(English shot list for video AI: {en})"


def resolve_creative_direction(
    user_input: str,
    variation_index: int = 0,
    style_analysis: dict[str, Any] | None = None,
    job_seed: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Trả về (text cho pipeline, metadata).
    Nếu user_input rỗng → prompt mặc định sinh động.
    """
    cleaned = (user_input or "").strip()
    if cleaned:
        return cleaned, {
            "source": "user",
            "key": "user",
            "label_vi": "Yêu cầu của bạn",
        }

    seed = hash(job_seed) % (2**31) if job_seed else None
    direction = pick_default_direction(variation_index, style_analysis, seed=seed)
    text = _build_prompt_text(direction)
    meta = {
        "source": "auto_default",
        "key": direction["key"],
        "label_vi": direction["label_vi"],
        "prompt_vi": direction["prompt_vi"],
        "prompt_en": direction["prompt_en"],
    }
    return text, meta


def list_default_direction_labels() -> list[dict[str, str]]:
    """Cho API / frontend — danh sách nhãn gợi ý."""
    return [{"key": d["key"], "label_vi": d["label_vi"]} for d in DEFAULT_VIDEO_DIRECTIONS]


def preview_default_for_variation(
    variation_index: int = 0,
    style_analysis: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Xem trước prompt mặc định sẽ dùng (không ghi vào job)."""
    d = pick_default_direction(variation_index, style_analysis)
    return {
        "key": d["key"],
        "label_vi": d["label_vi"],
        "prompt_vi": d["prompt_vi"],
        "preview_text": _build_prompt_text(d),
    }
