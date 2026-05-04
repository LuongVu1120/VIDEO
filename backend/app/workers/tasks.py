"""Pipeline: Orchestrates the full AI pipeline for architectural video generation.

Supports both Celery async (via process_job) and direct sync (via process_job_sync).
"""

import json
import base64
import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .celery_app import celery_app
from ..core.config import settings
from ..core.websocket import manager
from ..models.job import Job
from ..models.output import Output
from ..services.vision_analyzer import StyleAnalyzer
from ..services.prompt_writer import PromptWriter
from ..services.image_generator import ImageGenerator
from ..services.video_generator import VideoGenerator
from ..services.caption_writer import CaptionWriter
from ..services.music_suggester import MusicSuggester
from ..services.social_poster import SocialPoster


def _get_sync_db_url() -> str:
    """Get sync database URL with SQLite fallback."""
    sync_url = settings.DATABASE_URL_SYNC
    async_url = settings.DATABASE_URL

    # If async already switched to SQLite (e.g., arch_video.db exists), use SQLite sync
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "arch_video.db")
    if os.path.exists(db_path):
        return f"sqlite:///{db_path}"

    # If async URL is SQLite
    if async_url.startswith("sqlite"):
        return async_url.replace("+aiosqlite", "").replace("+asyncpg", "")

    # Try sync URL as-is
    if sync_url:
        return sync_url

    # Fallback to SQLite
    return f"sqlite:///{db_path}"


sync_engine = create_engine(_get_sync_db_url(), echo=False)
SyncSession = sessionmaker(bind=sync_engine)


def _send_ws_update(job_id: str, data: dict):
    """Send WebSocket update in a new event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.send_job_update(job_id, data))
        loop.close()
    except Exception:
        pass


def update_job_status(job_id: str, status: str, progress: int = None,
                      current_step: str = None, step_name: str = None):
    """Update job status in DB and send WebSocket notification."""
    db: Session = SyncSession()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = status
        if progress is not None:
            job.progress = progress
        if current_step is not None:
            job.current_step = current_step
        if step_name:
            steps = list(job.steps_completed) if isinstance(job.steps_completed, list) else []
            steps.append(step_name)
            job.steps_completed = steps
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    _send_ws_update(job_id, {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "current_step": current_step,
    })


# ======================================================================
# CELERY TASK (async, needs Redis or filesystem broker)
# ======================================================================

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_job(self, job_id: str, image_path: str, options: dict):
    """Celery task entry point."""
    try:
        _run_pipeline(job_id, image_path, options)
    except Exception as exc:
        _handle_pipeline_error(job_id, exc)
        raise self.retry(exc=exc)


# ======================================================================
# SYNC ENTRY POINT (chay trong thread rieng, khong can Celery/Redis)
# ======================================================================

def process_job_sync(job_id: str, image_path: str, options: dict):
    """Chay pipeline dong bo (goi truc tiep tu upload route)."""
    try:
        _run_pipeline(job_id, image_path, options)
    except Exception as exc:
        _handle_pipeline_error(job_id, exc)


# ======================================================================
# CORE PIPELINE LOGIC (dung chung cho ca Celery va Sync)
# ======================================================================

def _run_pipeline(job_id: str, image_path: str, options: dict):
    """Core pipeline: 7 buoc chinh."""
    platforms = options.get("platforms", ["instagram"])

    # ==================== STEP 1: VISION ANALYSIS ====================
    update_job_status(
        job_id, "processing", progress=5,
        current_step="Analyzing reference image style...",
        step_name="vision_analysis"
    )

    analyzer = StyleAnalyzer(provider="openai", use_trained_style=True)
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    style_analysis = analyzer.analyze(image_base64)
    style_data = json.loads(style_analysis) if isinstance(style_analysis, str) else style_analysis
    if not isinstance(style_data, dict):
        style_data = {"style": str(style_data)}

    # Generate creative variations
    update_job_status(
        job_id, "processing", progress=10,
        current_step="Generating creative architectural variations...",
        step_name="generate_variations"
    )

    variations = analyzer._analyze_variation_workflow(image_base64)
    all_results = []

    for idx, variation in enumerate(variations.get("variations", [])):
        variation_style = variation if isinstance(variation, dict) else {}
        blended_analysis = {
            **style_data,
            "variation_name": variation_style.get("variation_name", f"Variation {idx+1}"),
            "style": variation_style.get("style", style_data.get("style", "Contemporary")),
            "materials": variation_style.get("materials", style_data.get("materials", [])),
            "colors": variation_style.get("colors", style_data.get("colors", [])),
            "lighting": variation_style.get("lighting", style_data.get("lighting", "natural golden hour")),
            "mood": variation_style.get("mood", style_data.get("mood", "peaceful")),
            "key_features": variation_style.get("key_features", style_data.get("key_features", [])),
            "environment": variation_style.get("environment", style_data.get("environment", "natural")),
        }

        # ==================== STEP 2: PROMPT WRITING ====================
        update_job_status(
            job_id, "processing", progress=15 + (idx * 15),
            current_step=f"Writing prompts for {blended_analysis.get('variation_name', f'Variation {idx+1}')}...",
            step_name=f"prompt_writing_v{idx+1}"
        )

        prompt_writer = PromptWriter(use_deepseek=settings.USE_DEEPSEEK_FOR_PROMPTS)
        prompts_data = prompt_writer.generate_prompts(blended_analysis)
        prompts = json.loads(prompts_data) if isinstance(prompts_data, str) else prompts_data
        if not isinstance(prompts, dict):
            prompts = {"image_prompt": str(prompts_data), "video_prompt": "",
                      "negative_prompt": "", "style_tags": []}

        # ==================== STEP 3: IMAGE GENERATION ====================
        update_job_status(
            job_id, "processing", progress=20 + (idx * 15),
            current_step=f"Generating images for variation {idx+1}...",
            step_name=f"image_generation_v{idx+1}"
        )

        image_gen = ImageGenerator()
        images = image_gen.generate_images(
            prompt=prompts.get("image_prompt", ""),
            negative=prompts.get("negative_prompt", ""),
            n=options.get("num_images", 4),
        )

        # ==================== STEP 4: VIDEO GENERATION ====================
        video_url = None
        if options.get("generate_video", True) and images:
            update_job_status(
                job_id, "processing", progress=25 + (idx * 15),
                current_step=f"Generating video for variation {idx+1}...",
                step_name=f"video_generation_v{idx+1}"
            )
            video_gen = VideoGenerator()
            video_url = video_gen.generate(images[0], prompts.get("video_prompt", ""))

        all_results.append({
            "variation": blended_analysis,
            "prompts": prompts,
            "images": images,
            "video_url": video_url,
        })

    # ==================== STEP 5: CAPTION WRITING ====================
    update_job_status(
        job_id, "processing", progress=85,
        current_step="Writing captions and hashtags for all platforms...",
        step_name="caption_writing"
    )

    caption_writer = CaptionWriter(use_deepseek=settings.USE_DEEPSEEK_FOR_CAPTIONS)
    captions = {}
    for platform in platforms:
        caption_data = caption_writer.write_caption(style_data, platform)
        try:
            captions[platform] = json.loads(caption_data) if isinstance(caption_data, str) else caption_data
        except (json.JSONDecodeError, TypeError):
            captions[platform] = {"title": "", "caption": str(caption_data),
                                 "hashtags": [], "call_to_action": ""}

    # ==================== STEP 6: MUSIC SUGGESTION ====================
    update_job_status(
        job_id, "processing", progress=92,
        current_step="Selecting background music...",
        step_name="music_suggestion"
    )

    music_suggester = MusicSuggester(use_deepseek=settings.USE_DEEPSEEK_FOR_PROMPTS)
    music_suggestions = {}
    for platform in platforms:
        try:
            music_data = music_suggester.suggest_music(style_data, platform)
            music_suggestions[platform] = json.loads(music_data) if isinstance(music_data, str) else music_data
        except (json.JSONDecodeError, TypeError):
            music_suggestions[platform] = {"tracks": [], "platform_recommendation": ""}

    # ==================== STEP 7: SOCIAL MEDIA PREVIEW ====================
    update_job_status(
        job_id, "processing", progress=95,
        current_step="Preparing social media posts (dry run)...",
        step_name="social_preview"
    )

    social_poster = SocialPoster()
    first_result = all_results[0] if all_results else {}
    first_image = (first_result.get("images") or [None])[0]
    first_video = first_result.get("video_url")

    post_results = social_poster.post_to_all(
        image_url=first_image,
        video_url=first_video,
        captions=captions,
        dry_run=True,
    )

    # ==================== SAVE OUTPUT ====================
    db: Session = SyncSession()
    try:
        output = Output(
            job_id=job_id,
            style_analysis=style_data,
            variations=variations,
            prompts=[r["prompts"] for r in all_results],
            images=[img for r in all_results for img in (r.get("images") or [])],
            videos=[r["video_url"] for r in all_results if r.get("video_url")],
            captions=captions,
            music_suggestions=music_suggestions,
            social_post_preview=post_results,
            cost_usd=0.675 * (len(all_results) or 1),
        )
        db.add(output)

        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress = 100
            job.current_step = f"Completed! Generated {len(all_results)} variations."
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    _send_ws_update(job_id, {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "current_step": f"Generated {len(all_results)} variations across {len(platforms)} platforms!",
        "results_summary": {
            "variations": len(all_results),
            "total_images": sum(len(r.get("images") or []) for r in all_results),
            "videos": sum(1 for r in all_results if r.get("video_url")),
            "platforms": platforms,
        }
    })


def _handle_pipeline_error(job_id: str, exc: Exception):
    """Mark job as failed."""
    db: Session = SyncSession()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()

    _send_ws_update(job_id, {
        "job_id": job_id,
        "status": "failed",
        "error": str(exc),
    })
