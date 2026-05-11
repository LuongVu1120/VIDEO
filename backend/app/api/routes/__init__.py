from fastapi import APIRouter

router = APIRouter()

from .upload import router as upload_router
from .jobs import router as jobs_router
from .outputs import router as outputs_router
from .auth import router as auth_router
from .ws import router as ws_router

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(upload_router, prefix="/jobs", tags=["Jobs"])
router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
router.include_router(outputs_router, prefix="/outputs", tags=["Outputs"])
router.include_router(ws_router, tags=["WebSocket"])
from ..video_enhance import router as video_enhance_router
router.include_router(video_enhance_router, tags=["Video Enhance"])
from .ws_video import router as ws_video_router
router.include_router(ws_video_router, tags=["WebSocket Video"])
from ..pipeline_routes import router as pipeline_router
router.include_router(pipeline_router, tags=["Pipeline"])
