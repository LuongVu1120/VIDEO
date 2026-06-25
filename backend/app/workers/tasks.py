"""Pipeline: Orchestrates the full AI pipeline for architectural video generation.

Supports both Celery async (via process_job) and direct sync (via process_job_sync).
"""

import json
import base64
import asyncio
import os
import threading
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# ── Cancel flag registry ──────────────────────────────────────────────────────
# Maps job_id → threading.Event. Set the event to request cancellation.
_cancel_flags: dict[str, threading.Event] = {}
_cancel_flags_lock = threading.Lock()


def register_cancel_flag(job_id: str) -> threading.Event:
    """Create and store a cancel event for this job. Called before starting the thread."""
    event = threading.Event()
    with _cancel_flags_lock:
        _cancel_flags[job_id] = event
    return event


def request_cancel(job_id: str) -> bool:
    """Signal the pipeline thread to stop. Returns True if flag was found."""
    with _cancel_flags_lock:
        event = _cancel_flags.get(job_id)
    if event:
        event.set()
        return True
    return False


def _is_cancelled(job_id: str) -> bool:
    with _cancel_flags_lock:
        event = _cancel_flags.get(job_id)
    return event is not None and event.is_set()


def _cleanup_cancel_flag(job_id: str):
    with _cancel_flags_lock:
        _cancel_flags.pop(job_id, None)

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
from ..services.music_suggester import MusicSuggester, MUSIC_MOOD_MAP
from ..services.social_poster import SocialPoster
from ..services.watermark_service import apply_branding_to_job
from ..services.video_cost import estimate_fal_video_usd, clamp_duration_for_model
from ..services.bgm_service import apply_bgm_to_video, infer_bgm_mood
from ..services.default_video_directions import resolve_creative_direction


def _get_sync_db_url() -> str:
    """Get sync database URL with SQLite fallback — mirrors database.py logic."""
    async_url = settings.DATABASE_URL
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "arch_video.db")
    sqlite_url = f"sqlite:///{db_path}"

    if settings.FORCE_POSTGRES:
        sync_url = settings.DATABASE_URL_SYNC
        return sync_url if sync_url else async_url.replace("+asyncpg", "+psycopg2")

    # Same rule as database.py: postgresql+asyncpg in dev → use SQLite
    if async_url.startswith("postgresql+asyncpg"):
        return sqlite_url

    if async_url.startswith("sqlite"):
        return async_url.replace("+aiosqlite", "")

    return sqlite_url


def _sync_sqlite_pragma(dbapi_conn, connection_record):
    from ..core.database import _configure_sqlite_connection
    _configure_sqlite_connection(dbapi_conn, connection_record)


_sync_url = _get_sync_db_url()
_sync_connect_args = {"check_same_thread": False, "timeout": 30} if _sync_url.startswith("sqlite") else {}
sync_engine = create_engine(_sync_url, echo=False, connect_args=_sync_connect_args)
if _sync_url.startswith("sqlite"):
    event.listens_for(sync_engine, "connect")(_sync_sqlite_pragma)
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


def _make_stream_callback(job_id: str, step: str, batch_size: int = 80):
    """
    Returns an on_chunk callback that batches streaming tokens and sends them
    via WebSocket. Batching (every batch_size chars) avoids the overhead of
    creating a new event loop for every single token.
    """
    buffer: list[str] = []
    total: list[int] = [0]

    def flush():
        if not buffer:
            return
        text = "".join(buffer)
        buffer.clear()
        _send_ws_update(job_id, {
            "type": "stream_chunk",
            "step": step,
            "chunk": text,
        })

    def on_chunk(text: str):
        buffer.append(text)
        total[0] += len(text)
        if total[0] >= batch_size:
            flush()
            total[0] = 0

    # Expose flush so the caller can drain the buffer after streaming ends
    on_chunk.flush = flush
    return on_chunk


def update_job_status(job_id: str, status: str, progress: int = None,
                      current_step: str = None, step_name: str = None):
    """Update job status in DB and send WebSocket notification."""
    steps_snapshot = None
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
            steps_snapshot = steps
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    ws_payload = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "current_step": current_step,
    }
    if steps_snapshot is not None:
        ws_payload["steps_completed"] = steps_snapshot
    _send_ws_update(job_id, ws_payload)


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
    except _CancelledError:
        _handle_pipeline_cancelled(job_id)
    except Exception as exc:
        _handle_pipeline_error(job_id, exc)
    finally:
        _cleanup_cancel_flag(job_id)


# ======================================================================
# CORE PIPELINE LOGIC (dung chung cho ca Celery va Sync)
# ======================================================================

def _estimate_job_cost_usd(options: dict, all_results: list) -> float:
    """Rough USD estimate: vision/prompt/caption baseline + fal video + images."""
    variation_count = len(all_results) or 1
    base = 0.08 * variation_count if settings.COST_SAVE_MODE else 0.12 * variation_count
    num_images = sum(len(r.get("images") or []) for r in all_results)
    image_unit = 0.02 if settings.IMAGE_PROVIDER.startswith("sdxl") else (
        0.02 if settings.IMAGE_OPENAI_QUALITY == "low" else 0.04
    )
    image_cost = num_images * image_unit
    video_count = sum(1 for r in all_results if r.get("video_url"))
    if options.get("generate_video", True) and video_count:
        duration = clamp_duration_for_model(int(options.get("video_duration") or 5))
        video_cost = estimate_fal_video_usd(duration, video_count)
    else:
        video_cost = 0.0
    return round(base + image_cost + video_cost, 3)


def _run_pipeline(job_id: str, image_path: str, options: dict):
    """Core pipeline: 7 buoc chinh."""
    platforms = options.get("platforms", ["instagram", "facebook", "tiktok", "youtube"])
    if settings.COST_SAVE_MODE:
        # Caption 1 platform (instagram ưu tiên) — tiết kiệm ~75% API caption
        if "instagram" in platforms:
            platforms = ["instagram"]
        else:
            platforms = platforms[:1]

    user_description = options.get("user_description", "")

    # ==================== STEP 1: VISION ANALYSIS ====================
    _check_cancel(job_id)
    update_job_status(
        job_id, "processing", progress=5,
        current_step="Analyzing reference image style...",
        step_name="vision_analysis"
    )

    analyzer = StyleAnalyzer(provider="openai", use_trained_style=True)
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    style_analysis = analyzer.analyze(image_base64, user_description=user_description)
    style_data = json.loads(style_analysis) if isinstance(style_analysis, str) else style_analysis
    if not isinstance(style_data, dict):
        style_data = {"style": str(style_data)}

    # Generate creative variations — pass existing style_data to skip duplicate analyze() call
    _check_cancel(job_id)
    update_job_status(
        job_id, "processing", progress=10,
        current_step="Generating creative architectural variations...",
        step_name="generate_variations"
    )

    variations = analyzer._analyze_variation_workflow(image_base64, existing_analysis=style_data)
    all_results = []
    video_errors = []
    used_bgm_paths: list[str] = []

    variation_list = variations.get("variations", [])
    num_variations = len(variation_list) or 1
    # num_images is the TOTAL images requested — divide evenly across variations (0 = skip)
    num_images_total = max(0, int(options.get("num_images", 2)))
    if num_images_total == 0:
        images_per_variation = 0
    else:
        images_per_variation = max(1, num_images_total // num_variations)

    for idx, variation in enumerate(variation_list):
        _check_cancel(job_id)
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

        # Creative direction: user input hoặc prompt mặc định sinh động (ngày/đêm, mùa, room-in/out...)
        effective_desc, direction_meta = resolve_creative_direction(
            user_description,
            variation_index=idx,
            style_analysis=blended_analysis,
            job_seed=job_id,
        )
        if direction_meta.get("source") == "auto_default":
            print(
                f"[Creative] Auto direction v{idx+1}: {direction_meta.get('label_vi')} "
                f"({direction_meta.get('key')})"
            )

        # ==================== STEP 2: PROMPT WRITING (streaming) ====================
        variation_label = blended_analysis.get("variation_name", f"Variation {idx+1}")
        update_job_status(
            job_id, "processing", progress=15 + (idx * 15),
            current_step=f"Writing prompts for {variation_label}...",
            step_name=f"prompt_writing_v{idx+1}"
        )

        prompt_writer = PromptWriter(use_deepseek=settings.USE_DEEPSEEK_FOR_PROMPTS)
        prompt_cb = _make_stream_callback(job_id, f"prompt_v{idx+1}")
        prompts_data = prompt_writer.generate_prompts_streaming(
            blended_analysis, on_chunk=prompt_cb, user_description=effective_desc
        )
        prompt_cb.flush()
        prompts = json.loads(prompts_data) if isinstance(prompts_data, str) else prompts_data
        if not isinstance(prompts, dict):
            prompts = {"image_prompt": str(prompts_data), "video_prompt": "",
                      "negative_prompt": "", "style_tags": []}

        # ==================== STEP 3: IMAGE GENERATION ====================
        _check_cancel(job_id)
        images: list = []
        if images_per_variation > 0:
            update_job_status(
                job_id, "processing", progress=20 + (idx * 15),
                current_step=f"Generating images for variation {idx+1}...",
                step_name=f"image_generation_v{idx+1}"
            )
            image_gen = ImageGenerator()
            images = image_gen.generate_images(
                prompt=prompts.get("image_prompt", ""),
                negative=prompts.get("negative_prompt", ""),
                n=images_per_variation,
            )
        else:
            update_job_status(
                job_id, "processing", progress=20 + (idx * 15),
                current_step=f"Skipping image generation for variation {idx+1} (using upload only)...",
                step_name=f"image_generation_v{idx+1}"
            )

        # ==================== STEP 4: VIDEO GENERATION ====================
        _check_cancel(job_id)
        video_url = None
        video_source = images[0] if images else image_path
        max_video_variations = min(
            int(options.get("max_video_variations", settings.VIDEO_MAX_VARIATIONS)),
            settings.VIDEO_MAX_VARIATIONS,
        )
        max_video_variations = max(1, min(2, max_video_variations))

        if (
            options.get("generate_video", True)
            and video_source
            and idx < max_video_variations
        ):
            update_job_status(
                job_id, "processing", progress=25 + (idx * 15),
                current_step=f"Generating video for variation {idx+1}..."
            )
            video_gen = VideoGenerator()
            try:
                video_duration = clamp_duration_for_model(
                    int(options.get("video_duration") or 5)
                )
                video_url = video_gen.generate(
                    video_source,
                    prompts.get("video_prompt", ""),
                    duration_seconds=video_duration,
                    user_description=effective_desc,
                    negative_prompt=prompts.get("negative_prompt", ""),
                )
                update_job_status(
                    job_id, "processing", progress=25 + (idx * 15),
                    current_step=f"Generated video for variation {idx+1}.",
                    step_name=f"video_generation_v{idx+1}"
                )
            except Exception as e:
                video_error = f"Variation {idx+1}: {e}"
                video_errors.append(video_error)
                print(f"[Video] Generation failed for variation {idx+1}: {e}")
                update_job_status(
                    job_id, "processing", progress=25 + (idx * 15),
                    current_step=f"Video generation failed for variation {idx+1}: {e}"
                )

        # ==================== BRANDING / WATERMARK ====================
        _check_cancel(job_id)
        if settings.BRAND_NAME:
            update_job_status(
                job_id, "processing", progress=25 + (idx * 15),
                current_step=f"Applying brand watermark for variation {idx+1}...",
                step_name=f"watermark_v{idx+1}"
            )
            try:
                images, video_url = apply_branding_to_job(
                    job_id=f"{job_id}_v{idx+1}",
                    images=images,
                    video_url=video_url,
                    brand_name=settings.BRAND_NAME,
                    brand_phone=settings.BRAND_PHONE,
                    position=settings.BRAND_WATERMARK_POSITION,
                )
            except Exception as e:
                print(f"[Watermark] Skipped: {e}")

        # ==================== BACKGROUND MUSIC (FFmpeg) ====================
        bgm_meta: dict | None = None
        if video_url:
            _check_cancel(job_id)
            inferred = infer_bgm_mood(blended_analysis)
            variation_label = blended_analysis.get("variation_name", f"Variation {idx+1}")
            update_job_status(
                job_id, "processing", progress=25 + (idx * 15),
                current_step=f"Adding {inferred} background music for {variation_label}...",
                step_name=f"bgm_mux_v{idx+1}",
            )
            try:
                bgm_result = apply_bgm_to_video(
                    video_url,
                    mood=str(blended_analysis.get("mood", "peaceful")),
                    job_id=f"{job_id}_v{idx+1}",
                    style_analysis=blended_analysis,
                    variation_index=idx,
                    used_tracks=used_bgm_paths,
                )
                if bgm_result:
                    video_url = bgm_result["video_url"]
                    bgm_meta = bgm_result
                    used_bgm_paths.append(bgm_result["bgm_path"])
            except Exception as e:
                print(f"[BGM] Skipped for variation {idx+1}: {e}")

        prompts_record = dict(prompts)
        prompts_record["creative_direction"] = direction_meta
        if user_description:
            prompts_record["user_description"] = user_description
        all_results.append({
            "variation": blended_analysis,
            "prompts": prompts_record,
            "images": images,
            "video_url": video_url,
            "bgm": bgm_meta,
        })

    # ==================== STEP 5: CAPTION WRITING ====================
    _check_cancel(job_id)
    update_job_status(
        job_id, "processing", progress=85,
        current_step="Writing captions and hashtags for all platforms...",
        step_name="caption_writing"
    )

    caption_writer = CaptionWriter(use_deepseek=settings.USE_DEEPSEEK_FOR_CAPTIONS)
    captions = {}
    for platform in platforms:
        caption_cb = _make_stream_callback(job_id, f"caption_{platform}")
        # Returns {"vi": {...}, "en": {...}} in one API call
        captions[platform] = caption_writer.write_bilingual_caption_streaming(
            style_data, platform, on_chunk=caption_cb
        )
        caption_cb.flush()

    # ==================== STEP 6: MUSIC SUGGESTION ====================
    _check_cancel(job_id)
    update_job_status(
        job_id, "processing", progress=92,
        current_step="Selecting background music...",
        step_name="music_suggestion"
    )

    music_suggester = MusicSuggester(use_deepseek=settings.USE_DEEPSEEK_FOR_PROMPTS)
    music_suggestions = {}
    for platform in platforms:
        try:
            if settings.COST_SAVE_MODE:
                mood_key = str(style_data.get("mood", "peaceful")).lower()
                tracks = MUSIC_MOOD_MAP.get(mood_key, MUSIC_MOOD_MAP["peaceful"])
                music_suggestions[platform] = {
                    "tracks": tracks,
                    "platform_recommendation": f"Static BGM picks for {platform} (cost-save mode)",
                }
            else:
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
    first_image = (first_result.get("images") or [None])[0] or image_path
    first_video = first_result.get("video_url")
    all_videos = [r["video_url"] for r in all_results if r.get("video_url")]

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
            videos=all_videos,
            video_url=first_video,
            captions=captions,
            music_suggestions=music_suggestions,
            social_post_preview=post_results,
            cost_usd=_estimate_job_cost_usd(options, all_results),
        )
        db.add(output)

        job = db.query(Job).filter(Job.id == job_id).first()
        steps_snapshot = []
        if job:
            job.status = "completed"
            job.progress = 100
            job.current_step = f"Completed! Generated {len(all_results)} variations."
            steps_snapshot = (
                list(job.steps_completed)
                if isinstance(job.steps_completed, list)
                else []
            )
            if video_errors and not all_videos:
                job.error_message = "\n".join(video_errors)
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    _send_ws_update(job_id, {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "current_step": f"Completed! Generated {len(all_results)} variations.",
        "steps_completed": steps_snapshot,
        "results_summary": {
            "variations": len(all_results),
            "total_images": sum(len(r.get("images") or []) for r in all_results),
            "videos": sum(1 for r in all_results if r.get("video_url")),
            "platforms": platforms,
        }
    })


class _CancelledError(Exception):
    pass


def _check_cancel(job_id: str):
    """Raise _CancelledError if the job has been cancelled."""
    if _is_cancelled(job_id):
        raise _CancelledError(f"Job {job_id} was cancelled by user")


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


def _handle_pipeline_cancelled(job_id: str):
    """Mark job as cancelled."""
    db: Session = SyncSession()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "cancelled"
            job.error_message = "Stopped by user"
            job.updated_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()

    _send_ws_update(job_id, {
        "job_id": job_id,
        "status": "cancelled",
        "progress": job.progress if job else 0,
        "current_step": "Stopped by user",
    })
