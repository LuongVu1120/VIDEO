"""Video Enhancement API Routes - Extend the main pipeline with TTS + Video Composition."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..services.tts_service import TTSService
from ..services.video_composer import VideoComposer

router = APIRouter(prefix="/api/video/enhance", tags=["video-enhance"])
tts = TTSService()


# ==================== TTS Endpoints ====================

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    speed: float = 1.0
    filename: Optional[str] = None


class TTSResponse(BaseModel):
    audio_path: str
    duration: float
    voices: Optional[dict] = None


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest):
    """Generate narration audio from text using Edge TTS (free)."""
    try:
        result = await tts.synthesize_with_duration(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            output_dir="output/audio",
        )
        return TTSResponse(
            audio_path=result["path"],
            duration=result["duration"],
            voices=TTSService.list_voices(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def list_voices():
    """List all available TTS voices."""
    return TTSService.list_voices()


@router.get("/health")
async def health_check():
    """Check if TTS service is operational."""
    return {"status": "ok", "service": "Edge TTS (free)", "voices": len(TTSService.list_voices())}


# ==================== Video Composition Endpoints ====================

class ComposeRequest(BaseModel):
    video_path: str
    audio_path: str
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.15
    title: Optional[str] = None
    output_path: Optional[str] = None


class ComposeResponse(BaseModel):
    output_path: str
    duration: float


@router.post("/compose", response_model=ComposeResponse)
async def compose_video(request: ComposeRequest):
    """Compose final video with narration + BGM."""
    try:
        composer = VideoComposer()
        output = request.output_path or "output/video/composed.mp4"
        os.makedirs(os.path.dirname(output), exist_ok=True)

        result = composer.compose(
            video_path=request.video_path,
            audio_path=request.audio_path,
            bgm_path=request.bgm_path,
            bgm_volume=request.bgm_volume,
            title=request.title,
            output_path=output,
        )
        duration = composer.get_video_duration(result)
        return ComposeResponse(output_path=result, duration=duration)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ImageToVideoRequest(BaseModel):
    image_path: str
    audio_path: str
    fps: int = 30
    output_path: Optional[str] = None


@router.post("/image-to-video")
async def image_to_video(request: ImageToVideoRequest):
    """Create video from image + narration audio."""
    try:
        composer = VideoComposer()
        output = request.output_path or "output/video/image_to_video.mp4"
        result = composer.create_video_from_image(
            image_path=request.image_path,
            audio_path=request.audio_path,
            output_path=output,
            fps=request.fps,
        )
        duration = composer.get_video_duration(result)
        return {"output_path": result, "duration": duration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
