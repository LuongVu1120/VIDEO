"""WebSocket routes for real-time video generation status."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...core.websocket import manager

router = APIRouter(prefix="/ws", tags=["WebSocket-Video"])


@router.websocket("/generate/{job_id}")
async def video_generation_ws(websocket: WebSocket, job_id: str):
    """
    WebSocket for real-time video generation progress.
    
    Usage:
        ws://localhost:8000/api/v1/ws/generate/{job_id}
    
    Messages received (client -> server):
        { "command": "status" }  -> Get current status
        
    Messages sent (server -> client):
        { "type": "progress", "job_id": "...", "progress": 0.5, 
          "status": "processing", "message": "Generating narration...",
          "timestamp": "2025-01-15T10:30:00" }
        { "type": "completed", ... }
        { "type": "error", "error": "..." }
    """
    await manager.connect(job_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send commands (like "status")
            # For now, just keep alive - updates come from pipeline
            pass
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
    except Exception as e:
        await manager.send_job_update(job_id, {
            "type": "error",
            "job_id": job_id,
            "error": str(e),
        })
        manager.disconnect(job_id, websocket)
