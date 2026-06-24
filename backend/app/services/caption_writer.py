"""Step 5: Caption Writing - Generate social media captions using DeepSeek V4.

Mỗi platform trả về caption song ngữ: tiếng Việt + tiếng Anh trong 1 API call.
"""

import json
import re
from typing import Callable, Optional
from openai import OpenAI
from ..core.config import settings
from .caption_utils import (
    CAPTION_MAX_HASHTAGS,
    CAPTION_MIN_HASHTAGS,
    MAX_POST_CAPTION_WORDS,
    clamp_caption_fields,
)


_CAPTION_WORD_RULE = (
    f"caption body MUST be fewer than 20 words (maximum {MAX_POST_CAPTION_WORDS} words), "
    "short and punchy; call_to_action if any must also stay under 20 words"
)

_HASHTAG_RULE = (
    f"include exactly {CAPTION_MIN_HASHTAGS} to {CAPTION_MAX_HASHTAGS} relevant hashtags "
    "(architecture, interior, design, location/style); each with # prefix"
)

PLATFORM_CONFIGS = {
    "instagram": f"engaging, aesthetic, {_CAPTION_WORD_RULE}, {_HASHTAG_RULE}",
    "tiktok": f"trendy, hook in first line, {_CAPTION_WORD_RULE}, {_HASHTAG_RULE}",
    "youtube": f"SEO-friendly title (short), {_CAPTION_WORD_RULE}, {_HASHTAG_RULE}",
    "facebook": f"warm, community-focused, {_CAPTION_WORD_RULE}, {_HASHTAG_RULE}",
    "zalo": f"friendly, professional, {_CAPTION_WORD_RULE}, no hashtags needed",
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

        post_lang = (settings.CAPTION_POST_LANGUAGE or "vi").lower()
        if post_lang.startswith("vi"):
            post_note = (
                "- 'vi' is the REAL caption posted to social media — write natural, professional Vietnamese.\n"
                "- 'en' is an English translation for reference; keep the same meaning.\n"
            )
        else:
            post_note = (
                "- 'en' is the REAL caption posted to social media — write professional English.\n"
                "- 'vi' is a Vietnamese translation for the user to read.\n"
            )

        vi_mode = (settings.CONTENT_LANGUAGE or "vi").lower().startswith("vi")
        vi_note = (
            "The user works in Vietnamese. Hashtags may mix Vietnamese and English.\n"
            if vi_mode
            else ""
        )

        return [{
            "role": "user",
            "content": (
                f"Write a {platform} caption for architectural content with this style:\n"
                f"{json.dumps(style_analysis, indent=2, ensure_ascii=False)}\n\n"
                f"Requirements: {config}"
                f"{instruction_block}\n\n"
                "IMPORTANT:\n"
                f"- Each 'caption' field must be under 20 words (max {MAX_POST_CAPTION_WORDS} words).\n"
                f"- Each 'hashtags' array must have {CAPTION_MIN_HASHTAGS}-{CAPTION_MAX_HASHTAGS} items.\n"
                f"{vi_note}"
                f"{post_note}\n"
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
        fields = {
            "title": data.get("title", ""),
            "caption": data.get("caption", ""),
            "hashtags": data.get("hashtags", []),
            "call_to_action": data.get("call_to_action", ""),
        }
        return clamp_caption_fields(fields)

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
