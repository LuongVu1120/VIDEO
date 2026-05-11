"""Pipeline API Routes - Trigger video generation with WebSocket progress."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
import asyncio
import os

from ..services.video_pipeline import VideoPipeline
from ..core.websocket import manager

router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])


class NarrationRequest(BaseModel):
    script: str
    voice: str = "en-US-JennyNeural"
    speed: float = 1.0
    job_id: Optional[str] = None


class ComposeRequest(BaseModel):
    video_path: str
    audio_path: str
    bgm_path: Optional[str] = None
    job_id: Optional[str] = None


class PipelineResponse(BaseModel):
    job_id: str
    status: str
    message: str
    websocket_url: str


@router.post("/narration", response_model=PipelineResponse)
async def generate_narration(request: NarrationRequest):
    """
    Start narration generation with real-time WebSocket progress.

    Connect to ws://localhost:8000/api/v1/ws/generate/{job_id}
    to receive progress updates.
    """
    job_id = request.job_id or str(uuid4())

    # Start async task
    asyncio.create_task(_run_narration(job_id, request))

    return PipelineResponse(
        job_id=job_id,
        status="started",
        message="Narration generation started",
        websocket_url=f"/api/v1/ws/generate/{job_id}"
    )


async def _run_narration(job_id: str, request: NarrationRequest):
    """Run narration generation in background, sending progress via WS."""
    try:
        await manager.send_job_update(job_id, {
            "type": "started",
            "job_id": job_id,
            "status": "starting",
            "message": f"Starting TTS with voice: {request.voice}",
        })

        pipeline = VideoPipeline()
        result = await pipeline.generate_narration(
            script=request.script,
            voice=request.voice,
            speed=request.speed,
            job_id=job_id,
        )

        await manager.send_job_update(job_id, {
            "type": "completed",
            "job_id": job_id,
            "status": "completed",
            "progress": 1.0,
            "message": "Narration generated successfully",
            "result": {
                "audio_path": result["path"],
                "duration": result["duration"],
            },
            "voices": list(TTSService.list_voices().keys())[:5] if False else []
        })
    except Exception as e:
        await manager.send_job_update(job_id, {
            "type": "error",
            "job_id": job_id,
            "error": str(e),
        })


@router.post("/compose", response_model=PipelineResponse)
async def compose_video(request: ComposeRequest):
    """Start video composition with real-time WebSocket progress."""
    job_id = request.job_id or str(uuid4())

    asyncio.create_task(_run_compose(job_id, request))

    return PipelineResponse(
        job_id=job_id,
        status="started",
        message="Video composition started",
        websocket_url=f"/api/v1/ws/generate/{job_id}"
    )


async def _run_compose(job_id: str, request: ComposeRequest):
    """Run video composition in background."""
    try:
        await manager.send_job_update(job_id, {
            "type": "started",
            "job_id": job_id,
            "status": "starting",
            "message": "Starting video composition...",
        })

        pipeline = VideoPipeline()
        final_path = await pipeline.compose_final_video(
            video_path=request.video_path,
            audio_path=request.audio_path,
            bgm_path=request.bgm_path,
            job_id=job_id,
        )

        await manager.send_job_update(job_id, {
            "type": "completed",
            "job_id": job_id,
            "status": "completed",
            "progress": 1.0,
            "message": "Video composition complete",
            "result": {
                "output_path": final_path,
            }
        })
    except Exception as e:
        await manager.send_job_update(job_id, {
            "type": "error",
            "job_id": job_id,
            "error": str(e),
        })
