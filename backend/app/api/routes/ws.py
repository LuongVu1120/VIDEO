"""WebSocket route for real-time job status updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...core.websocket import manager

router = APIRouter()


@router.websocket("/ws/job/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
