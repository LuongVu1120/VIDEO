from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db
from .api.routes import router as api_router
from .services.scheduler_service import start_scheduler, stop_scheduler

# Ensure output folder exists (served as static files for branded images/videos)
# backend/app/main.py → parent.parent = backend/ → output = backend/output/
_OUTPUT_DIR = Path(__file__).parent.parent / "output"
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router, prefix="/api/v1")

# Serve branded output files (watermarked images & videos)
# Access via: GET /output/{job_id}/image_1_branded.jpg
app.mount("/output", StaticFiles(directory=str(_OUTPUT_DIR)), name="output")


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
