# Copyright (C) 2025 - Ported from Pixelle-Video (Apache 2.0)
"""Video Composition Service - Combine cinematic footage + narration + BGM + overlays."""

import os
import tempfile
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class VideoComposerError(Exception):
    pass


class VideoComposer:
    """Video composition service — 9:16 portrait for mobile.
    Combines: cinematic video + narration audio + background music + text overlays.
    """

    # Mobile portrait dimensions (9:16)
    VIDEO_WIDTH = 1080
    VIDEO_HEIGHT = 1920

    def __init__(self):
        self._ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            print("[WARN] FFmpeg not found. Install it for video composition.")

    def compose(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.15,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> str:
        """
        Compose final video with narration + background music.

        Args:
            video_path: Path to cinematic video (from Veo/Runway)
            audio_path: Path to narration audio (from TTS)
            output_path: Where to save final video
            bgm_path: Optional background music path
            bgm_volume: BGM volume (0.0-1.0)
            title: Optional title text for overlay
            subtitle: Optional subtitle text for overlay

        Returns:
            Path to final composed video
        """
        # Step 1: Add narration audio to video
        temp_with_narration = self._add_audio_to_video(
            video_path, audio_path, output_path.replace(".mp4", "_with_audio.mp4")
        )

        # Step 2: Add BGM if provided
        if bgm_path and os.path.exists(bgm_path):
            final_output = self._add_bgm_to_video(
                temp_with_narration, bgm_path, output_path, bgm_volume
            )
            # Cleanup temp
            if os.path.exists(temp_with_narration):
                os.unlink(temp_with_narration)
            return final_output
        else:
            # Rename temp to final
            shutil.move(temp_with_narration, output_path)
            return output_path

    def create_video_from_image(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        fps: int = 30,
    ) -> str:
        """Create video from static image + audio (slideshow style)."""
        try:
            probe = json.loads(
                subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
                    capture_output=True, text=True, timeout=10,
                ).stdout
            )
            duration = float(probe["format"]["duration"])
        except Exception:
            duration = 10.0

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={self.VIDEO_WIDTH}:{self.VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={self.VIDEO_WIDTH}:{self.VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-b:v", "2M",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return output_path

    def overlay_text_on_video(
        self,
        video_path: str,
        text: str,
        output_path: str,
        position: str = "bottom",
    ) -> str:
        """Add text overlay to video using FFmpeg drawtext."""
        y_pos = "h-text_h-50" if position == "bottom" else "50"

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", (
                f"drawtext=text='{text}':"
                f"fontcolor=white:fontsize=48:"
                f"box=1:boxcolor=black@0.4:boxborderw=10:"
                f"x=(w-text_w)/2:y={y_pos}:"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
            "-c:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return output_path

    def concat_videos(self, video_paths: list, output_path: str) -> str:
        """Concatenate multiple videos."""
        # Create file list
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            for v in video_paths:
                f.write(f"file '{v}'\n")
            filelist = f.name

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", filelist, "-c", "copy", output_path],
                check=True, capture_output=True, timeout=300
            )
            return output_path
        finally:
            if os.path.exists(filelist):
                os.unlink(filelist)

    def _add_audio_to_video(self, video: str, audio: str, output: str) -> str:
        """Replace/add narration audio to video."""
        # Probe video for audio stream
        try:
            probe = json.loads(
                subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video],
                    capture_output=True, text=True, timeout=10,
                ).stdout
            )
            has_audio = any(s["codec_type"] == "audio" for s in probe.get("streams", []))
        except Exception:
            has_audio = False

        if has_audio:
            # Replace audio
            cmd = [
                "ffmpeg", "-y",
                "-i", video,
                "-i", audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output,
            ]
        else:
            # Add audio to silent video
            cmd = [
                "ffmpeg", "-y",
                "-i", video,
                "-i", audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output,
            ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return output

    def _add_bgm_to_video(self, video: str, bgm: str, output: str, volume: float = 0.15) -> str:
        """Add background music mixed with original audio."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video,
            "-i", bgm,
            "-filter_complex",
            f"[1:a]volume={volume},adelay=1|1[a1];"
            f"[0:a][a1]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return output

    def get_video_duration(self, video_path: str) -> float:
        try:
            probe = json.loads(
                subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
                    capture_output=True, text=True, timeout=10,
                ).stdout
            )
            return float(probe["format"]["duration"])
        except Exception:
            return 0.0

