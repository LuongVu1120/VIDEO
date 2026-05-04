"""Step 6: Music Suggestion - Suggest suitable background music for architectural videos."""

import json
import re
from openai import OpenAI
from ..core.config import settings


# Danh sach nhac public domain / royalty-free phu hop voi kien truc
MUSIC_MOOD_MAP = {
    "peaceful": [
        {"title": "Ambient Piano", "mood": "calm", "bpm": 60},
        {"title": "Soft Strings", "mood": "serene", "bpm": 50},
        {"title": "Gentle Waves", "mood": "relaxing", "bpm": 55},
    ],
    "luxurious": [
        {"title": "Elegant Jazz", "mood": "sophisticated", "bpm": 70},
        {"title": "Modern Classical", "mood": "premium", "bpm": 65},
        {"title": "Cinematic Strings", "mood": "grand", "bpm": 75},
    ],
    "dramatic": [
        {"title": "Epic Cinematic", "mood": "powerful", "bpm": 85},
        {"title": "Dark Ambient", "mood": "mysterious", "bpm": 70},
        {"title": "Tension Build", "mood": "intense", "bpm": 80},
    ],
    "cozy": [
        {"title": "Acoustic Guitar", "mood": "warm", "bpm": 60},
        {"title": "Soft Folk", "mood": "homely", "bpm": 55},
        {"title": "Lo-fi Beats", "mood": "chill", "bpm": 70},
    ],
    "futuristic": [
        {"title": "Synthwave", "mood": "futuristic", "bpm": 90},
        {"title": "Electronic Minimal", "mood": "modern", "bpm": 80},
        {"title": "Digital Ambience", "mood": "tech", "bpm": 75},
    ],
    "serene": [
        {"title": "Nature Soundscape", "mood": "organic", "bpm": 45},
        {"title": "Zen Meditation", "mood": "spiritual", "bpm": 40},
        {"title": "Minimal Piano", "mood": "pure", "bpm": 55},
    ],
}


class MusicSuggester:
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

    def suggest_music(self, style_analysis: dict, platform: str = "instagram") -> str:
        """Suggest background music based on architectural style and platform."""
        mood = style_analysis.get("mood", "peaceful").lower()
        style = style_analysis.get("style", "Contemporary")

        # Map mood to music
        base_music = MUSIC_MOOD_MAP.get(mood, MUSIC_MOOD_MAP["peaceful"])

        kwargs = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": f"""Suggest 3 background music tracks for a {platform} video showcasing {style} architecture.
The video mood is "{mood}".

Base music options to consider: {json.dumps(base_music)}

For each track, provide:
- title: track name
- artist_or_source: where to find it (Epidemic Sound, Artlist, Uppbeat, etc.)
- mood: emotional quality
- bpm: beats per minute
- duration: recommended clip duration in seconds (15s for Reels, 30s for Shorts, 60s for TikTok)
- why_it_fits: 1 sentence explanation

Return JSON: {{"tracks": [{{"title", "artist_or_source", "mood", "bpm", "duration", "why_it_fits"}}], "platform_recommendation": "advice on music for {platform}"}}
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
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text
