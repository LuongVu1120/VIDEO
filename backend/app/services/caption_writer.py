"""Step 5: Caption Writing - Generate social media captions using DeepSeek V4.

Mỗi platform trả về caption song ngữ: tiếng Việt + tiếng Anh trong 1 API call.
"""

import json
import re
from typing import Callable, Optional
from openai import OpenAI
from ..core.config import settings


PLATFORM_CONFIGS = {
    "instagram": "engaging, aesthetic, 150-200 words, 20-25 hashtags",
    "tiktok": "trendy, hook in first line, 80-100 words, 5-10 hashtags",
    "youtube": "descriptive, SEO-friendly title + description, 3-5 hashtags",
    "facebook": "warm, community-focused, 100-150 words, 10-15 hashtags",
    "zalo": "friendly, professional, 80-120 words, no hashtags needed",
}


class CaptionWriter:
    def __init__(self, use_deepseek: bool = True):
        if use_deepseek:
            self.client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
            self.model = settings.DEEPSEEK_MODEL
            self.use_deepseek = True
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = "gpt-4o-mini"
            self.use_deepseek = False

    # ------------------------------------------------------------------
    # Bilingual (vi + en) — primary method used by the pipeline
    # ------------------------------------------------------------------

    def _build_bilingual_messages(
        self, style_analysis: dict, platform: str, extra_instruction: str = ""
    ) -> list:
        config = PLATFORM_CONFIGS.get(platform, PLATFORM_CONFIGS["instagram"])
        instruction_block = (
            f"\n\nADDITIONAL INSTRUCTION FROM USER:\n{extra_instruction}\n"
            "Apply this while keeping the caption professional and architecture-focused."
        ) if extra_instruction.strip() else ""

        return [{
            "role": "user",
            "content": (
                f"Write a {platform} caption for architectural content with this style:\n"
                f"{json.dumps(style_analysis, indent=2, ensure_ascii=False)}\n\n"
                f"Requirements: {config}"
                f"{instruction_block}\n\n"
                "IMPORTANT:\n"
                "- 'en' is the REAL caption that will be posted to social media. Write it professionally in English.\n"
                "- 'vi' is a Vietnamese TRANSLATION of the English caption, shown only so the user understands what will be posted. "
                "It must faithfully reflect the English version — do NOT create different content.\n\n"
                "Return JSON with this exact structure:\n"
                "{\n"
                '  "en": {"title": "...", "caption": "...", "hashtags": ["#...", "..."], "call_to_action": "..."},\n'
                '  "vi": {"title": "...", "caption": "...", "hashtags": ["#...", "..."], "call_to_action": "..."}\n'
                "}"
            ),
        }]

    def write_bilingual_caption(
        self, style_analysis: dict, platform: str = "instagram", extra_instruction: str = ""
    ) -> dict:
        """Generate caption in both Vietnamese and English (non-streaming)."""
        kwargs = {
            "model": self.model,
            "messages": self._build_bilingual_messages(style_analysis, platform, extra_instruction),
        }
        if not self.use_deepseek:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return self._parse_bilingual(content)

    def write_bilingual_caption_streaming(
        self,
        style_analysis: dict,
        platform: str = "instagram",
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Streaming bilingual caption.
        Calls on_chunk(text) for each token.
        Returns dict {"vi": {...}, "en": {...}} when complete.
        """
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self._build_bilingual_messages(style_analysis, platform),
            stream=True,
        )
        full_text = ""
        for chunk in stream:
            delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
            if delta:
                full_text += delta
                if on_chunk:
                    on_chunk(delta)

        return self._parse_bilingual(full_text)

    def _parse_bilingual(self, text: str) -> dict:
        """Parse bilingual JSON response into {"vi": {...}, "en": {...}}."""
        raw = self._extract_json(text)
        try:
            data = json.loads(raw)
            vi = data.get("vi") or {}
            en = data.get("en") or {}
            # Fallback: if model returned flat structure (no vi/en keys), wrap it
            if not vi and not en:
                vi = en = data
            return {
                "vi": self._ensure_caption_fields(vi),
                "en": self._ensure_caption_fields(en),
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "vi": self._empty_caption(),
                "en": self._empty_caption(),
            }

    # ------------------------------------------------------------------
    # Single-language fallback (kept for backwards compat)
    # ------------------------------------------------------------------

    def write_caption(self, style_analysis: dict, platform: str = "instagram", language: str = "vi") -> str:
        """Single-language caption (non-streaming). Returns JSON string."""
        config = PLATFORM_CONFIGS.get(platform, PLATFORM_CONFIGS["instagram"])
        if language == "vi":
            lang_note = "Viết hoàn toàn bằng tiếng Việt. Hashtag có thể kết hợp tiếng Việt và tiếng Anh."
        else:
            lang_note = "Write entirely in English."

        messages = [{
            "role": "user",
            "content": (
                f"Write a {platform} caption for architectural content with this style:\n"
                f"{json.dumps(style_analysis, indent=2, ensure_ascii=False)}\n\n"
                f"Language: {lang_note}\n"
                f"Requirements: {config}\n\n"
                '{"title": "...", "caption": "...", "hashtags": ["#..."], "call_to_action": "..."}'
            ),
        }]
        kwargs = {"model": self.model, "messages": messages}
        if not self.use_deepseek:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return self._extract_json(content) if self.use_deepseek else content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_caption_fields(self, data: dict) -> dict:
        return {
            "title": data.get("title", ""),
            "caption": data.get("caption", ""),
            "hashtags": data.get("hashtags", []),
            "call_to_action": data.get("call_to_action", ""),
        }

    def _empty_caption(self) -> dict:
        return {"title": "", "caption": "", "hashtags": [], "call_to_action": ""}

    def _extract_json(self, text: str) -> str:
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text
