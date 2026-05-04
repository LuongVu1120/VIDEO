"""Step 1: Vision Analysis - Analyze architecture image using GPT-4o (OpenAI).

Phân tích ảnh tham khảo, trích xuất style và tạo biến thể kiến trúc
mới có cùng phong cách nhưng không giống y hệt.
"""

import json
import re
from openai import OpenAI
from ..core.config import settings
from ..core.trained_style import get_trained_style_summary


class StyleAnalyzer:
    def __init__(self, provider: str = "openai", use_trained_style: bool = True):
        self.provider = provider
        self.trained_style_summary = ""
        # Load style profile da hoc tu TRAIN AI dataset (neu duoc yeu cau)
        if use_trained_style:
            try:
                self.trained_style_summary = get_trained_style_summary() or ""
            except Exception:
                self.trained_style_summary = ""

    def analyze(self, image_base64: str) -> str:
        """
        Phân tích ảnh tham khảo, trích xuất style chi tiết.
        Tra ve JSON string.
        """
        trained_context = ""
        if self.trained_style_summary:
            trained_context = f"""
The user has a trained architectural style profile from analyzing multiple reference images.
When analyzing the new image, cross-reference its style with the user's known preferences below.
Note how the new image relates to or differs from the user's established style.

{self.trained_style_summary}

When extracting fields, also add a "similarity_to_trained" field:
- "high": fits well with user's trained style
- "medium": partially overlaps
- "low": different from user's usual style
"""

        prompt = f"""
        Analyze this architecture image and extract detailed information.
        This image is a REFERENCE for generating NEW architectural designs.
        The goal is to understand the style deeply so we can create VARIATIONS.

        {trained_context}

        Extract these fields (be as specific and detailed as possible):
        - style: The architectural style (Contemporary / Modern Minimalist / Neoclassical / Mediterranean / Industrial / Brutalist / Tropical / Scandinavian / etc.)
        - materials: list of specific visible materials (include surface finishes like "brushed concrete", "warm oak wood", "low-e glass", "weathered steel", "limestone", etc.)
        - colors: primary color palette (list specific color names like "warm beige", "cool gray #B0B0B0", "charcoal black", "terracotta #E2725B", "olive green")
        - lighting: lighting conditions (natural golden hour / soft diffused overcast / dramatic shadows / warm sunset / cool blue hour / bright midday / etc.)
        - mood: emotional tone (peaceful / dramatic / luxurious / cozy / futuristic / serene / bold / elegant / etc.)
        - architecture_type: (house / villa / mansion / commercial / interior / landscape / urban / apartment / etc.)
        - environment: surrounding context (urban / suburban / natural / waterfront / mountain / garden / forest / desert / coastal / etc.)
        - key_features: list of distinctive architectural features (cantilever, green roof, floor-to-ceiling windows, open plan, pool, terrace, etc.)
        - time_of_day: (morning / midday / golden hour / blue hour / night / twilight / etc.)
        - camera_perspective: (eye-level / low angle / aerial / worm's-eye view / straight-on / three-quarter view / etc.)
        - composition: (symmetrical / asymmetrical / rule of thirds / leading lines / framing / centered / etc.)
        - similarity_to_trained: how similar this image is to user's trained style profile ("high" / "medium" / "low")

        Respond in JSON format only. Do not wrap in markdown code blocks. Do not include any other text.
        """

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
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
        return self._ensure_json(content)

    def generate_variation_directions(self, style_analysis: dict) -> str:
        """
        Tao huong dan bien the kien truc tu anh tham khao.
        Output: JSON voi 3-4 bien the khac nhau, moi bien the co style khac biet
        nhung van giu tinh than kien truc goc.
        """
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        style = style_analysis.get("style", "Contemporary")
        materials = ", ".join(style_analysis.get("materials", ["glass", "wood"])[:5])
        colors = ", ".join(style_analysis.get("colors", ["white", "gray"])[:5])
        lighting = style_analysis.get("lighting", "natural daylight")
        mood = style_analysis.get("mood", "peaceful")
        features = ", ".join(style_analysis.get("key_features", ["large windows"])[:5])
        environment = style_analysis.get("environment", "natural")

        prompt = f"""You are an expert architect and AI art director. Based on a reference building analysis,
        generate 4 CREATIVE VARIATIONS of the architectural design.

        REFERENCE STYLE: {style}
        REFERENCE MATERIALS: {materials}
        REFERENCE COLORS: {colors}
        REFERENCE LIGHTING: {lighting}
        REFERENCE MOOD: {mood}
        REFERENCE FEATURES: {features}
        REFERENCE ENVIRONMENT: {environment}

        RULES FOR VARIATIONS:
        1. Each variation must have the SAME architectural "DNA" (proportions, layout logic, structural concept)
        2. But DIFFERENT: materials, color palette, specific details, or expression of the style
        3. Keep logical architectural integrity - no impossible structures
        4. Maintain beautiful composition and camera angles
        5. Each variation should feel like a different architect's take on the same design brief

        For each variation provide:
        - variation_name: short name
        - style: architectural style for this variation (can be a sub-style or fusion)
        - materials: specific materials
        - colors: color palette (3-5 colors)
        - lighting: ideal lighting condition
        - mood: emotional tone
        - key_features: key architectural features
        - environment: environment setting
        - rationale: 1 sentence explaining how this differs from the original

        Return JSON: {{"variations": [...]}}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.85,  # Higher temperature for creativity
        )
        content = response.choices[0].message.content
        return self._ensure_json(content)

    def _analyze_variation_workflow(self, image_base64: str) -> dict:
        """
        Workflow hoan chinh: phan tich anh -> tao bien the -> tra ve ca hai.
        """
        # Step 1: Analyze reference
        analysis_str = self.analyze(image_base64)
        analysis = json.loads(analysis_str)

        # Step 2: Generate variations
        variations_str = self.generate_variation_directions(analysis)
        variations = json.loads(variations_str)

        return {
            "reference_analysis": analysis,
            "variations": variations.get("variations", []),
        }

    def _get_trained_count(self) -> int:
        """Lấy số ảnh training từ style guide nếu có."""
        try:
            from ..core.trained_style import load_style_guide
            guide = load_style_guide()
            if guide:
                return guide.get("total_images_analyzed", 0)
        except Exception:
            pass
        return 0

    def _ensure_json(self, text: str) -> str:
        """Ensure the response is valid JSON, extracting from markdown if needed."""
        if not text or not text.strip():
            return json.dumps({
                "style": "Modern Minimalist",
                "materials": ["concrete", "glass"],
                "colors": ["#FFFFFF", "#808080"],
                "lighting": "natural daylight",
                "mood": "modern",
                "architecture_type": "house",
                "environment": "urban",
                "key_features": ["clean lines"],
                "time_of_day": "morning",
                "camera_perspective": "eye-level",
                "composition": "symmetrical",
            })

        # Try to find JSON in ```json ... ``` blocks
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON object directly
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return text
