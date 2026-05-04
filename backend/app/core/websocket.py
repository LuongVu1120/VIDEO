from typing import Dict
from fastapi import WebSocket
import json


class ConnectionManager:
    """Manages WebSocket connections for real-time job status updates."""

    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def send_job_update(self, job_id: str, data: dict):
        """Send a status update to all clients watching this job."""
        if job_id not in self.active_connections:
            return
        message = json.dumps(data)
        disconnected = []
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(job_id, conn)


manager = ConnectionManager()
