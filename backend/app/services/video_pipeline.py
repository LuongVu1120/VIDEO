import os
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from .tts_service import TTSService
from .video_composer import VideoComposer
from ..core.websocket import manager


class VideoPipeline:
    """
    End-to-end video generation pipeline with WebSocket progress updates.

    Steps:
    1. Generate narration audio (TTS)
    2. Compose final video (cinematic + narration + BGM)
    """

    def __init__(self):
        self.tts = TTSService()
        self.composer = VideoComposer()
        self.output_dir = "output"
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(f"{self.output_dir}/audio", exist_ok=True)
        os.makedirs(f"{self.output_dir}/video", exist_ok=True)
        os.makedirs(f"{self.output_dir}/frames", exist_ok=True)

    async def _send_progress(self, job_id: str, progress: float, status: str, message: str = "", details: dict = None):
        """Send progress update via WebSocket."""
        data = {
            "type": "progress",
            "job_id": job_id,
            "progress": progress,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        if details:
            data["details"] = details
        await manager.send_job_update(job_id, data)

    async def generate_narration(
        self,
        script: str,
        voice: str = "en-US-JennyNeural",
        speed: float = 1.0,
        job_id: str = None,
    ) -> dict:
        """
        Step 1: Generate narration audio from script text.

        Args:
            script: Text to convert to speech
            voice: TTS voice ID
            speed: Speech speed multiplier
            job_id: Optional job ID for WebSocket updates

        Returns:
            dict with "path" and "duration"
        """
        if job_id:
            await self._send_progress(job_id, 0.0, "processing", "Starting TTS generation...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"narration_{timestamp}.mp3"

        if job_id:
            await self._send_progress(job_id, 0.2, "processing", f"Generating narration ({len(script.split())} words)...")

        result = await self.tts.synthesize_with_duration(
            text=script,
            voice=voice,
            speed=speed,
            output_dir=f"{self.output_dir}/audio",
        )

        if job_id:
            await self._send_progress(
                job_id, 0.5, "completed", "Narration generated!",
                details={"audio_path": result["path"], "duration": result["duration"]}
            )

        return result

    async def compose_final_video(
        self,
        video_path: str,
        audio_path: str,
        bgm_path: Optional[str] = None,
        title: Optional[str] = None,
        job_id: str = None,
    ) -> str:
        """
        Step 2: Compose final video with progress updates.

        Args:
            video_path: Path to cinematic video
            audio_path: Path to narration audio
            bgm_path: Optional path to background music
            title: Optional title text
            job_id: Optional job ID for WebSocket updates

        Returns:
            Path to final video
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{self.output_dir}/video/final_{timestamp}.mp4"

        if job_id:
            await self._send_progress(job_id, 0.6, "processing", "Composing video with narration...")

        # Add audio to video (60% -> 80%)
        temp_with_audio = output_path.replace(".mp4", "_with_audio.mp4")
        if job_id:
            final_path = self.composer.compose(
                video_path=video_path,
                audio_path=audio_path,
                bgm_path=bgm_path,
                output_path=output_path,
                title=title,
            )
        else:
            final_path = self.composer.compose(
                video_path=video_path,
                audio_path=audio_path,
                bgm_path=bgm_path,
                output_path=output_path,
                title=title,
            )

        if job_id:
            duration = self.composer.get_video_duration(final_path) if hasattr(self.composer, 'get_video_duration') else 0
            await self._send_progress(
                job_id, 1.0, "completed", "Video generation complete!",
                details={
                    "output_path": final_path,
                    "duration": duration,
                    "size_mb": round(os.path.getsize(final_path) / (1024*1024), 2) if os.path.exists(final_path) else 0
                }
            )

        return final_path

    async def generate_slideshow_video(
        self,
        image_paths: list,
        audio_paths: list,
        bgm_path: Optional[str] = None,
        job_id: str = None,
    ) -> str:
        """
        Create video from multiple image+audio segments.

        Args:
            image_paths: List of image paths
            audio_paths: List of matching audio paths
            bgm_path: Optional background music
            job_id: Optional job ID for WebSocket updates

        Returns:
            Path to final video
        """
        if len(image_paths) != len(audio_paths):
            raise ValueError("image_paths and audio_paths must have same length")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        segments = []

        total = len(image_paths)
        for i, (img, aud) in enumerate(zip(image_paths, audio_paths)):
            if job_id:
                progress = 0.5 + (i / total) * 0.4
                await self._send_progress(
                    job_id, progress, "processing",
                    f"Processing segment {i+1}/{total}..."
                )

            seg_path = f"{self.output_dir}/video/seg_{timestamp}_{i}.mp4"
            seg = self.composer.create_video_from_image(img, aud, seg_path)
            segments.append(seg)

        # Concatenate
        if job_id:
            await self._send_progress(job_id, 0.9, "processing", "Concatenating segments...")

        if len(segments) == 1:
            final_path = f"{self.output_dir}/video/final_{timestamp}.mp4"
            import shutil
            shutil.move(segments[0], final_path)
        else:
            final_path = f"{self.output_dir}/video/final_{timestamp}.mp4"
            final_path = self.composer.concat_videos(segments, final_path)

        if job_id:
            await self._send_progress(
                job_id, 1.0, "completed", "Slideshow video complete!",
                details={"output_path": final_path, "segments": total}
            )

        return final_path
