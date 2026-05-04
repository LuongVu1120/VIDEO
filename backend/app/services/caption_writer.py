"""Step 5: Caption Writing - Generate social media captions using DeepSeek V4."""

import json
import re
from openai import OpenAI
from ..core.config import settings


class CaptionWriter:
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
            self.model = "gpt-4o-mini"
            self.use_deepseek = False

    def write_caption(self, style_analysis: dict, platform: str = "instagram") -> str:
        platform_configs = {
            "instagram": "engaging, aesthetic, 150-200 words, 20-25 hashtags",
            "tiktok": "trendy, hook in first line, 80-100 words, 5-10 hashtags",
            "youtube": "descriptive, SEO-friendly title + description, 3-5 hashtags"
        }

        config = platform_configs.get(platform, platform_configs["instagram"])

        kwargs = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": f"""
                Write a {platform} caption for architectural content with this style:
                {json.dumps(style_analysis, indent=2)}

                Requirements: {config}

                Return JSON: {{"title": "caption title", "caption": "full caption text", "hashtags": ["tag1", "tag2"], "call_to_action": "cta text"}}
                """
            }],
        }

        if not self.use_deepseek:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        if self.use_deepseek:
            content = self._extract_json(content)

        return content

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks."""
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text
