"""Step 2: Prompt Writing - Generate optimized prompts for image and video generation."""

import json
import re
from openai import OpenAI
from ..core.config import settings
from ..core.trained_style import load_system_prompt
from ..core.trained_video_style import load_video_system_prompt, get_trained_video_style_summary


# === PROMPT TEMPLATE CHUAN ===
# Template nay duoc thiet ke de tao anh kien truc chat luong cao,
# dung cam bien thuc te, khong co CGI look.
IMAGE_PROMPT_TEMPLATE = """A high-end architectural exterior of a {style} house,
featuring {materials}, clean composition, realistic proportions,
shot in {lighting_condition}, using {camera_type}.

Real-life architectural photography, captured with a full-frame DSLR camera,
natural lighting, realistic shadows, subtle reflections,
true-to-life materials, accurate textures, slight imperfections,
global illumination, soft ambient occlusion.

Balanced composition, professional architectural photography,
shot with 24mm wide-angle lens, depth of field, natural perspective,
realistic exposure, HDR photography, cinematic tone.

Ultra realistic, 8k, sharp focus, high dynamic range,
real-world lighting behavior, no CGI look.

--no distortion, bad proportions, unrealistic structure,
overly perfect surfaces, 3d render look, cartoon, artificial lighting"""

VIDEO_PROMPT_TEMPLATE = """Cinematic architectural exterior of a {style} house,
gentle slow orbit around the house showcasing {features},
{lighting_condition} with warm sunlight casting natural shadows,
full-frame DSLR quality, smooth 24fps motion,
architectural documentary style, professional grade,
4k ultra HD, no distortion, realistic materials."""


class PromptWriter:
    def __init__(self, use_deepseek: bool = True):
        if use_deepseek:
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL
            )
            self.model = settings.DEEPSEEK_MODEL
            self.use_deepseek = True
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o"
            self.use_deepseek = False

        # Load trained system prompts (đã học từ TRAIN AI dataset + VIDEO dataset)
        self.trained_system_prompt = load_system_prompt()
        self.trained_video_system_prompt = load_video_system_prompt()
        self.trained_video_summary = get_trained_video_style_summary()

    def generate_prompts(self, style_analysis: dict) -> str:
        """
        Tao prompt su dung template chuan, khop voi style analysis.
        Tra ve JSON: {image_prompt, video_prompt, negative_prompt, style_tags}
        """
        # Trich xuat cac field tu style analysis
        style = style_analysis.get("style", "Contemporary")
        materials_list = style_analysis.get("materials", ["glass", "wood", "stone"])
        materials_str = ", ".join(materials_list[:4])
        lighting = style_analysis.get("lighting", "natural golden hour")
        mood = style_analysis.get("mood", "peaceful")
        features_list = style_analysis.get("key_features", ["large windows", "clean lines"])
        features_str = ", ".join(features_list[:4])
        environment = style_analysis.get("environment", "natural landscape")
        time_of_day = style_analysis.get("time_of_day", "golden hour")
        camera_perspective = style_analysis.get("camera_perspective", "eye-level")

        # Xac dinh loai may anh dua tren lighting
        if "golden" in lighting.lower() or "sunset" in lighting.lower():
            camera_type = "Canon EOS R5 with 24mm f/1.4L II USM lens"
        elif "blue" in lighting.lower() or "night" in lighting.lower():
            camera_type = "Sony A7R IV with 16-35mm f/2.8 GM lens, long exposure"
        else:
            camera_type = "Nikon Z8 with 24mm f/1.8 S lens"

        # Dieu chinh camera perspective description
        if camera_perspective == "low angle":
            camera_desc = "low angle view emphasizing the structure's grandeur, shot with 16mm ultra wide-angle lens"
        elif camera_perspective == "aerial":
            camera_desc = "aerial perspective from slightly elevated position, shot with 50mm tilt-shift lens"
        elif camera_perspective == "worm's-eye view":
            camera_desc = "dramatic worm's-eye view looking upward, shot with 14mm ultra wide-angle lens"
        else:
            camera_desc = "eye-level view, shot with 24mm wide-angle lens, natural perspective"

        # Su dung trained system prompt neu co
        if self.trained_system_prompt:
            system_prompt = self.trained_system_prompt
        else:
            system_prompt = """
You are an expert architectural photographer and AI art director.
Generate precise, detailed prompts for AI image and video generation
based on architectural style analysis. Always output valid JSON.
"""

        # Them video-trained context neu co
        video_context = ""
        if self.trained_video_summary:
            video_context = f"""
## TRAINED VIDEO STYLE (from analyzing reference videos)
{self.trained_video_summary}
"""
        if self.trained_video_system_prompt:
            system_prompt += f"\n\n### VIDEO STYLE PROFILE\n{self.trained_video_system_prompt}"

        user_prompt = f"""You are generating prompts for a {style} house in a {environment} setting.

## STYLE ANALYSIS INPUT
- Style: {style}
- Materials: {materials_str}
- Lighting: {lighting} ({time_of_day})
- Mood: {mood}
- Key features: {features_str}
- Camera: {camera_desc}
- Environment: {environment}

{video_context}

## TASK
Using the EXACT template structure below (fill in the blanks with the analysis above),
generate a complete prompt set. The template must be followed precisely for image_prompt.
For video_prompt, ADAPT the template using the trained video style profile above
(signature camera movement, speed, pacing, perspective).

### Image Prompt Template (MUST follow this structure exactly):
A high-end architectural exterior of a [style] house,
featuring [materials], clean composition, realistic proportions,
shot in [lighting condition], using [camera type].

Real-life architectural photography, captured with a full-frame DSLR camera,
natural lighting, realistic shadows, subtle reflections,
true-to-life materials, accurate textures, slight imperfections,
global illumination, soft ambient occlusion.

Balanced composition, professional architectural photography,
shot with 24mm wide-angle lens, depth of field, natural perspective,
realistic exposure, HDR photography, cinematic tone.

Ultra realistic, 8k, sharp focus, high dynamic range,
real-world lighting behavior, no CGI look.

--no distortion, bad proportions, unrealistic structure,
overly perfect surfaces, 3d render look, cartoon, artificial lighting

### Video Prompt Template (adapt to ~100 words, using trained video style):
{video_context if video_context else "A cinematic slow orbit around a [style] house,"}
showcasing [features] with [lighting] casting natural shadows,
peaceful atmosphere, smooth camera movement,
realistic architectural video, cinematic 24fps,
professional grade footage, 4k ultra HD.

### Output JSON format:
{{
  "image_prompt": "filled template above",
  "video_prompt": "adapted video prompt ~80-120 words",
  "negative_prompt": "distorted, low quality, blurry, unnatural colors, oversaturated, warped perspective, cartoonish, 3d render look, CGI, bad proportions, unrealistic materials, artificial lighting",
  "style_tags": ["#ContemporaryArchitecture", "#ModernHouse", "#ArchitecturalDesign", "#LuxuryHome", "#ArchitecturePhotography"]
}}

CRITICAL: The image_prompt MUST follow the exact template structure.
CRITICAL: The image_prompt MUST be a single continuous string, NOT broken into multiple lines in JSON.
CRITICAL: Generate 6-10 relevant style_tags based on the style analysis."""

        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
        }

        # OpenAI supports response_format, DeepSeek does not
        if not self.use_deepseek:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content

        # Ensure valid JSON (DeepSeek may return markdown-wrapped JSON)
        if self.use_deepseek:
            content = self._extract_json(content)

        # Validate and fill template as fallback
        try:
            result = json.loads(content)
            if not result.get("image_prompt") or len(result["image_prompt"]) < 50:
                result["image_prompt"] = self._fill_image_template(
                    style, materials_str, lighting, camera_type
                )
            if not result.get("video_prompt") or len(result["video_prompt"]) < 30:
                result["video_prompt"] = self._fill_video_template(
                    style, features_str, lighting
                )
            content = json.dumps(result, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # Fallback: build from templates directly
            fallback = {
                "image_prompt": self._fill_image_template(style, materials_str, lighting, camera_type),
                "video_prompt": self._fill_video_template(style, features_str, lighting),
                "negative_prompt": "distorted, low quality, blurry, unnatural colors, oversaturated, warped perspective, cartoonish, 3d render look, CGI, bad proportions, unrealistic materials, artificial lighting",
                "style_tags": [f"#{style.replace(' ', '')}", "#ModernHouse", "#Architecture", "#ArchitecturalDesign", "#LuxuryHome"],
            }
            content = json.dumps(fallback, ensure_ascii=False)

        return content

    def _fill_image_template(self, style: str, materials: str, lighting: str, camera: str) -> str:
        """Fill the standard image prompt template."""
        return (
            f"A high-end architectural exterior of a {style} house, "
            f"featuring {materials}, clean composition, realistic proportions, "
            f"shot in {lighting}, using {camera}. "
            f"Real-life architectural photography, captured with a full-frame DSLR camera, "
            f"natural lighting, realistic shadows, subtle reflections, "
            f"true-to-life materials, accurate textures, slight imperfections, "
            f"global illumination, soft ambient occlusion. "
            f"Balanced composition, professional architectural photography, "
            f"shot with 24mm wide-angle lens, depth of field, natural perspective, "
            f"realistic exposure, HDR photography, cinematic tone. "
            f"Ultra realistic, 8k, sharp focus, high dynamic range, "
            f"real-world lighting behavior, no CGI look. "
            f"--no distortion, bad proportions, unrealistic structure, "
            f"overly perfect surfaces, 3d render look, cartoon, artificial lighting"
        )

    def _fill_video_template(self, style: str, features: str, lighting: str) -> str:
        """Fill the standard video prompt template."""
        return (
            f"A cinematic slow orbit around a {style} house, "
            f"showcasing {features} with {lighting} casting natural shadows, "
            f"peaceful atmosphere, smooth camera movement, "
            f"realistic architectural video, cinematic 24fps, "
            f"professional grade footage, 4k ultra HD, no distortion, "
            f"realistic materials, natural lighting behavior."
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks."""
        # Try to find JSON in ```json ... ``` blocks
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Try to find JSON object directly
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text
