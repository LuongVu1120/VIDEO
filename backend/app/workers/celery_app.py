"""
Celery app configuration.
Tự động dùng Redis nếu có, fallback về file-based broker.
"""

import os
import socket
from celery import Celery
from ..core.config import settings


def _redis_available() -> bool:
    """Check if Redis is reachable."""
    hosts = [
        ("127.0.0.1", 6379),
    ]
    for host, port in hosts:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((host, port))
            s.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            continue
    return False


def _get_broker():
    """Return broker URL based on what's available."""
    redis_url = settings.REDIS_URL

    # Docker compose: redis://redis:6379 -> localhost fallback
    if "redis://redis:" in redis_url:
        redis_local = redis_url.replace("redis://redis:", "redis://127.0.0.1:")
        if _redis_available():
            print("[Celery] Using Redis at localhost")
            return redis_local, redis_local

    if redis_url and _redis_available():
        print(f"[Celery] Using Redis: {redis_url}")
        return redis_url, redis_url

    # Fallback: SQLite backend + file broker
    print("[Celery] Redis not available — using SQLite backend + file broker")
    print("[Celery] Install Redis for production: winget install Redis.Redis")

    celery_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'celery_data')
    os.makedirs(os.path.join(celery_dir, 'broker', 'in'), exist_ok=True)
    os.makedirs(os.path.join(celery_dir, 'broker', 'out'), exist_ok=True)
    os.makedirs(os.path.join(celery_dir, 'broker', 'processed'), exist_ok=True)

    # Dung file scheme
    broker_url = "filesystem://"
    backend_url = f"db+sqlite:///{celery_dir}/celery_backend.db"

    return broker_url, backend_url


broker_url, backend_url = _get_broker()

celery_app = Celery(
    "arch_video_generator",
    broker=broker_url,
    backend=backend_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# File-based broker config
if broker_url.startswith("filesystem"):
    celery_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'celery_data')
    celery_app.conf.update(
        broker_transport_options={
            "data_folder_in": os.path.join(celery_dir, 'broker', 'in'),
            "data_folder_out": os.path.join(celery_dir, 'broker', 'out'),
            "data_folder_processed": os.path.join(celery_dir, 'broker', 'processed'),
        },
        # SQLite backend da duoc set o tren
    )

print(f"[Celery] Broker: {broker_url}")
print(f"[Celery] Backend: {backend_url}")
