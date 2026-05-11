# Copyright (C) 2025 - Ported from Pixelle-Video (Apache 2.0)
"""TTS Service - Edge TTS integration (free, no API key)"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional
import edge_tts
from edge_tts.exceptions import NoAudioReceived
from aiohttp import WSServerHandshakeError, ClientResponseError


AVAILABLE_VOICES = {
    "en-US-JennyNeural": "Jenny (Female, US)",
    "en-US-GuyNeural": "Guy (Male, US)",
    "en-US-AriaNeural": "Aria (Female, US)",
    "en-US-DavisNeural": "Davis (Male, US)",
    "en-GB-SoniaNeural": "Sonia (Female, UK)",
    "en-GB-RyanNeural": "Ryan (Male, UK)",
    "en-AU-NatashaNeural": "Natasha (Female, AU)",
    "zh-CN-XiaoxiaoNeural": "Xiaoxiao (Female, CN)",
    "zh-CN-YunjianNeural": "Yunjian (Male, CN)",
    "zh-CN-YunxiNeural": "Yunxi (Male, CN)",
    "ko-KR-SunHiNeural": "Sun-Hi (Female, KR)",
    "ja-JP-NanamiNeural": "Nanami (Female, JP)",
    "fr-FR-DeniseNeural": "Denise (Female, FR)",
    "de-DE-KatjaNeural": "Katja (Female, DE)",
    "pt-BR-FranciscaNeural": "Francisca (Female, BR)",
    "ru-RU-SvetlanaNeural": "Svetlana (Female, RU)",
    "es-ES-ElviraNeural": "Elvira (Female, ES)",
}


class TTSError(Exception):
    pass


class TTSService:
    """Text-to-Speech using Edge TTS (Microsoft) - FREE."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(3)
        self._retry_count = 3

    async def synthesize(
        self,
        text: str,
        voice: str = "en-US-JennyNeural",
        speed: float = 1.0,
        output_dir: str = "output/audio",
        filename: Optional[str] = None,
    ) -> str:
        """Convert text to speech. Returns path to audio file."""
        if not text or not text.strip():
            raise TTSError("Text cannot be empty")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        if filename:
            audio_path = str(output_path / filename)
        else:
            unique_id = uuid.uuid4().hex[:12]
            audio_path = str(output_path / f"tts_{unique_id}.mp3")
        rate = self._speed_to_rate(speed)
        async with self._semaphore:
            last_error = None
            for attempt in range(self._retry_count + 1):
                try:
                    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
                    audio_chunks = []
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_chunks.append(chunk["data"])
                    if not audio_chunks:
                        raise TTSError("No audio data generated")
                    audio_data = b"".join(audio_chunks)
                    with open(audio_path, "wb") as f:
                        f.write(audio_data)
                    return audio_path
                except (WSServerHandshakeError, ClientResponseError) as e:
                    last_error = e
                    if attempt < self._retry_count:
                        await asyncio.sleep(2 ** attempt)
                except NoAudioReceived as e:
                    last_error = e
                    if attempt < self._retry_count:
                        await asyncio.sleep(3)
                except Exception as e:
                    raise TTSError(f"TTS failed: {e}")
            raise TTSError(f"TTS failed after retries: {last_error}")

    async def synthesize_with_duration(
        self,
        text: str,
        voice: str = "en-US-JennyNeural",
        speed: float = 1.0,
        output_dir: str = "output/audio",
    ) -> dict:
        audio_path = await self.synthesize(text=text, voice=voice, speed=speed, output_dir=output_dir)
        duration = self._get_audio_duration(audio_path)
        return {"path": audio_path, "duration": duration}

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            import subprocess, json
            result = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
                                    capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            import os
            return max(1.0, os.path.getsize(audio_path) / 2000)

    def _speed_to_rate(self, speed: float) -> str:
        percentage = int((speed - 1.0) * 100)
        sign = "+" if percentage >= 0 else ""
        return f"{sign}{percentage}%"

    @staticmethod
    def list_voices() -> dict:
        return AVAILABLE_VOICES.copy()
