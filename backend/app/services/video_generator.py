"""Step 4: Video Generation - Generate cinematic video from image."""

import time
import base64
import os
import requests
from pathlib import Path
from ..core.config import settings
from .video_cost import clamp_duration_for_model

_BACKEND_DIR = Path(__file__).parent.parent.parent  # VIDEO/backend/

# Kling image-to-video: vague prompts often become simple 2D pan/zoom on the still frame.
KLING_DEFAULT_NEGATIVE = (
    "simple 2D image pan, sliding still photo, ken burns only, floating static image, "
    "jitter, choppy motion, warped perspective, blur, low quality, distorted architecture"
)


def compose_kling_video_prompt(video_prompt: str, user_description: str = "") -> str:
    """Merge AI video prompt with user creative direction for fal/Kling."""
    parts: list[str] = []
    if user_description.strip():
        parts.append(
            "CREATIVE DIRECTION (highest priority — follow exactly; may be Vietnamese): "
            f"{user_description.strip()}"
        )
    if video_prompt and video_prompt.strip():
        parts.append(video_prompt.strip())
    else:
        parts.append(
            "Cinematic architectural video with motivated camera movement "
            "(slow dolly push-in or smooth orbit around the building), "
            "realistic parallax and depth, stable structure, natural lighting."
        )
    parts.append(
        "Camera work must be three-dimensional cinematic motion, not a flat photo sliding "
        "up/down/left/right. No simple Ken Burns pan on a still image."
    )
    return " ".join(parts)


class VideoGenerator:
    def generate(
        self,
        image_url_or_path: str,
        prompt: str,
        duration_seconds: int | None = None,
        *,
        user_description: str = "",
        negative_prompt: str = "",
    ) -> str:
        """Generate video using fal.ai, Google Veo 3.1, or Runway.
        Raises an exception if no provider returns a real video URL."""
        errors = []
        provider = (settings.VIDEO_PROVIDER or "fal").lower().strip()
        allow_fallback = provider == "auto"

        if provider in ("fal", "auto"):
            if not settings.FAL_KEY:
                if provider == "fal":
                    raise RuntimeError("Video generation skipped: FAL_KEY is not configured")
            else:
                try:
                    return self._generate_fal(
                        image_url_or_path,
                        prompt,
                        duration_seconds,
                        user_description=user_description,
                        negative_prompt=negative_prompt,
                    )
                except Exception as e:
                    errors.append(f"fal.ai: {e}")
                    print(f"fal.ai video generation failed: {e}")
                    if not allow_fallback:
                        raise RuntimeError("Video generation failed: " + " | ".join(errors))

        if provider in ("veo", "google"):
            if not settings.GOOGLE_API_KEY:
                raise RuntimeError("Video generation skipped: GOOGLE_API_KEY is not configured")
            try:
                veo_prompt = compose_kling_video_prompt(prompt, user_description)
                return self._generate_veo(image_url_or_path, veo_prompt)
            except Exception as e:
                raise RuntimeError(f"Video generation failed: Google Veo 3.1: {e}") from e

        if provider == "runway":
            if not settings.RUNWAY_API_KEY:
                raise RuntimeError("Video generation skipped: RUNWAY_API_KEY is not configured")
            try:
                runway_prompt = compose_kling_video_prompt(prompt, user_description)
                return self._generate_runway(image_url_or_path, runway_prompt, duration_seconds)
            except Exception as e:
                raise RuntimeError(f"Video generation failed: Runway: {e}") from e

        # Fallback chain only when VIDEO_PROVIDER=auto.
        if allow_fallback and settings.GOOGLE_API_KEY:
            try:
                veo_prompt = compose_kling_video_prompt(prompt, user_description)
                return self._generate_veo(image_url_or_path, veo_prompt)
            except Exception as e:
                errors.append(f"Google Veo 3.1: {e}")
                print(f"Google Veo 3.1 failed: {e}")

        if allow_fallback and settings.RUNWAY_API_KEY:
            try:
                runway_prompt = compose_kling_video_prompt(prompt, user_description)
                return self._generate_runway(image_url_or_path, runway_prompt, duration_seconds)
            except Exception as e:
                errors.append(f"Runway: {e}")
                print(f"Runway fallback also failed: {e}")

        if errors:
            raise RuntimeError("Video generation failed: " + " | ".join(errors))
        raise RuntimeError(f"Video generation skipped: unsupported VIDEO_PROVIDER='{provider}'")

    # ==================== fal.ai ====================

    def _generate_fal(
        self,
        image_url_or_path: str,
        prompt: str,
        duration_seconds: int | None = None,
        *,
        user_description: str = "",
        negative_prompt: str = "",
    ) -> str:
        """Generate image-to-video through fal.ai."""
        if not settings.FAL_KEY:
            raise ValueError("FAL_KEY not configured")

        try:
            import fal_client
        except ImportError as exc:
            raise RuntimeError(
                "fal-client is not installed. Run: pip install -r backend/requirements.txt"
            ) from exc

        os.environ["FAL_KEY"] = settings.FAL_KEY

        endpoint = settings.FAL_VIDEO_MODEL
        self._verify_fal_storage_auth()
        image_url = self._prepare_fal_image_url(image_url_or_path, fal_client)
        final_prompt = compose_kling_video_prompt(prompt, user_description)
        arguments = self._build_fal_arguments(
            endpoint,
            image_url,
            final_prompt,
            duration_seconds,
            negative_prompt=negative_prompt,
        )

        print(f"fal.ai video endpoint: {endpoint}")
        print(f"fal.ai video prompt ({len(final_prompt)} chars): {final_prompt[:400]}...")
        if user_description.strip():
            print(f"fal.ai user creative direction applied: {user_description[:200]}")
        result = fal_client.subscribe(
            endpoint,
            arguments=arguments,
            with_logs=True,
            on_queue_update=self._on_fal_queue_update,
            client_timeout=settings.FAL_VIDEO_TIMEOUT_SECONDS,
        )

        video_url = self._extract_fal_video_url(result)
        if not video_url:
            raise Exception(f"fal.ai: No video URL in response: {result}")

        print(f"fal.ai video generated: {video_url}")
        return video_url

    def _verify_fal_storage_auth(self) -> None:
        """Fail early with fal.ai's detailed auth error before uploading files."""
        response = requests.post(
            "https://rest.fal.ai/storage/auth/token?storage_type=fal-cdn-v3",
            headers={
                "Authorization": f"Key {settings.FAL_KEY}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={},
            timeout=20,
        )
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(f"fal.ai auth failed ({response.status_code}): {detail}")

    def _prepare_fal_image_url(self, image_url_or_path: str, fal_client) -> str:
        """Return a public image URL usable by fal video endpoints."""
        if image_url_or_path.startswith("http://") or image_url_or_path.startswith("https://"):
            return image_url_or_path

        local_path = self._resolve_local_path(image_url_or_path)
        return fal_client.upload_file(str(local_path))

    def _build_fal_arguments(
        self,
        endpoint: str,
        image_url: str,
        prompt: str,
        duration_seconds: int | None = None,
        *,
        negative_prompt: str = "",
    ) -> dict:
        """Build endpoint-specific fal arguments."""
        image_key = (
            "start_image_url"
            if "/o3/" in endpoint or "/v3/" in endpoint
            else "image_url"
        )
        raw_duration = duration_seconds if duration_seconds else int(settings.FAL_VIDEO_DURATION or 5)
        duration = clamp_duration_for_model(raw_duration, endpoint)
        arguments = {
            image_key: image_url,
            "prompt": prompt or compose_kling_video_prompt("", ""),
            "duration": str(duration),
        }

        if settings.FAL_VIDEO_GENERATE_AUDIO:
            arguments["generate_audio"] = True

        # Kling (O3 / turbo): stronger prompt adherence + block cheap pan-only motion
        if "/kling-video/" in endpoint:
            neg_parts = [KLING_DEFAULT_NEGATIVE]
            if negative_prompt and negative_prompt.strip():
                neg_parts.append(negative_prompt.strip())
            arguments["negative_prompt"] = ", ".join(neg_parts)
            arguments["cfg_scale"] = 0.65

        return arguments

    @staticmethod
    def _on_fal_queue_update(update):
        """Print fal queue logs when available."""
        logs = getattr(update, "logs", None) or []
        for log in logs:
            message = log.get("message") if isinstance(log, dict) else str(log)
            if message:
                print(f"fal.ai: {message}")

    @staticmethod
    def _extract_fal_video_url(result: dict) -> str:
        """Extract a video URL from common fal response shapes."""
        if not isinstance(result, dict):
            return ""

        for key in ("video", "output", "url", "video_url"):
            candidate = result.get(key)
            if isinstance(candidate, str):
                return candidate
            if isinstance(candidate, dict) and candidate.get("url"):
                return candidate["url"]
            if isinstance(candidate, list) and candidate:
                first = candidate[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict) and first.get("url"):
                    return first["url"]

        videos = result.get("videos")
        if isinstance(videos, list) and videos:
            first = videos[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict) and first.get("url"):
                return first["url"]

        return ""

    # ==================== Google Veo 3.1 (Gemini API) ====================

    def _generate_veo(self, image_url_or_path: str, prompt: str) -> str:
        """Generate video using Google Veo 3.1 via Gemini API (REST)."""
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not configured")

        # Get image as base64
        image_data = self._get_image_base64(image_url_or_path)
        mime_type = "image/png" if image_url_or_path.endswith(".png") else "image/jpeg"

        # Step 1: Create prediction (predictLongRunning)
        operation_resp = self._create_veo_task(api_key, image_data, prompt, mime_type)

        operation_name = operation_resp.get("name")
        if not operation_name:
            raise Exception(f"Veo: No operation name in response: {operation_resp}")

        print(f"Veo operation created: {operation_name}")

        # Step 2: Poll until done (video gen takes 2-5 minutes)
        max_attempts = 40  # ~6 minutes with 10s intervals
        for attempt in range(max_attempts):
            status_resp = self._get_veo_operation(api_key, operation_name)

            done = status_resp.get("done", False)
            if done:
                response_data = status_resp.get("response", {})
                generated_videos = response_data.get("generatedVideos", [])

                if not generated_videos:
                    # Check for error
                    error_info = status_resp.get("error", response_data.get("error"))
                    raise Exception(
                        f"Veo: Generation failed - {error_info or 'No generated videos in response'}"
                    )

                video = generated_videos[0]
                video_uri = video.get("video", {}).get("uri", "")
                if not video_uri:
                    # Try downloading using the file ID
                    video_file = video.get("video", {})
                    video_name = video_file.get("name", "")
                    if video_name:
                        video_uri = self._download_veo_video(api_key, video_name)
                    else:
                        raise Exception("Veo: No video URI or name in response")

                print(f"Veo video generated: {video_uri}")
                return video_uri

            print(f"Veo status: {status_resp.get('metadata', {}).get('state', 'RUNNING')}, "
                  f"attempt={attempt+1}/{max_attempts}")

            time.sleep(10)

        raise TimeoutError("Google Veo video generation timed out")

    def _create_veo_task(self, api_key: str, image_base64: str, prompt: str, mime_type: str = "image/jpeg") -> dict:
        """Create a Veo 3.1 image-to-video task via predictLongRunning."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/veo-3.1-generate-preview:predictLongRunning"
        )

        payload = {
            "instances": [
                {
                    "prompt": prompt,
                    "image": {
                        "bytesBase64Encoded": image_base64,
                        "mimeType": mime_type
                    }
                }
            ],
            "parameters": {
                "aspectRatio": "9:16",
                "personGeneration": "allow_adult",
                "numberOfVideos": 1
            }
        }

        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            json=payload,
            timeout=30
        )

        if response.status_code == 403:
            raise Exception(
                "Google Veo API: Forbidden. Check your API key has Veo access "
                "(need Google AI Plan subscription, ~$20/month)."
            )
        if response.status_code == 429:
            raise Exception("Google Veo API: Rate limited. Try again later.")
        if response.status_code == 400:
            raise Exception(f"Google Veo API: Bad request - {response.text}")

        response.raise_for_status()
        return response.json()

    def _get_veo_operation(self, api_key: str, operation_name: str) -> dict:
        """Get the status of a Veo operation."""
        url = f"https://generativelanguage.googleapis.com/v1beta/{operation_name}"

        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            timeout=30
        )

        if response.status_code >= 400:
            raise Exception(f"Google Veo operation status failed ({response.status_code}): {response.text}")
        return response.json()

    def _download_veo_video(self, api_key: str, video_name: str) -> str:
        """Get a signed URL to download the generated video."""
        url = f"https://generativelanguage.googleapis.com/v1beta/{video_name}"

        response = requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        # The file should have a downloadUri
        download_uri = data.get("downloadUri", "")
        if not download_uri:
            download_uri = data.get("uri", "")
        if not download_uri:
            # Generate a download URL from the file name
            file_id = video_name.split("/")[-1]
            download_uri = (
                f"https://generativelanguage.googleapis.com/v1beta/files/{file_id}?alt=media"
            )

        return download_uri

    def _resolve_to_bytes(self, image_url_or_path: str) -> bytes:
        """Return raw image bytes regardless of whether input is URL or path."""
        if image_url_or_path.startswith("http://") or image_url_or_path.startswith("https://"):
            resp = requests.get(image_url_or_path, timeout=60)
            resp.raise_for_status()
            return resp.content
        # /output/images/gen_xxx.png → backend/output/images/gen_xxx.png
        local_path = self._resolve_local_path(image_url_or_path)
        with open(local_path, "rb") as f:
            return f.read()

    def _resolve_local_path(self, image_url_or_path: str) -> Path:
        """Resolve app URL paths such as /output/images/x.png to local files."""
        if image_url_or_path.startswith("/output"):
            return _BACKEND_DIR / image_url_or_path.lstrip("/")
        return Path(image_url_or_path)

    def _get_image_base64(self, image_url_or_path: str) -> str:
        """Fetch an image and return its base64-encoded content."""
        return base64.b64encode(self._resolve_to_bytes(image_url_or_path)).decode("utf-8")

    # ==================== Runway ML (Fallback) ====================

    def _generate_runway(self, image_url: str, prompt: str, duration_seconds: int | None = None) -> str:
        """Runway image-to-video fallback."""
        headers = {
            "Authorization": f"Bearer {settings.RUNWAY_API_KEY}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06"
        }

        # Runway requires https:// URL or data:image/... base64
        if image_url.startswith("http://") or image_url.startswith("https://"):
            prompt_image = image_url
        else:
            img_bytes = self._resolve_to_bytes(image_url)
            prompt_image = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"

        # 9:16 portrait for mobile phones (TikTok/Reels/Shorts)
        payload = {
            "model": "gen3a_turbo",
            "promptImage": prompt_image,
            "promptText": prompt,
            "ratio": "768:1280",
            "duration": duration_seconds or 10,
            "watermark": False
        }

        response = requests.post(
            "https://api.dev.runwayml.com/v1/image_to_video",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 402:
            raise Exception("Runway API: Insufficient credits.")
        if response.status_code == 401:
            raise Exception("Runway API: Invalid API key.")
        if response.status_code == 400:
            raise Exception(f"Runway API: Bad request - {response.text}")

        response.raise_for_status()
        result = response.json()

        if result.get("status") == "SUCCEEDED" and result.get("output"):
            return result["output"][0]

        task_id = result.get("id")
        if not task_id:
            raise Exception(f"Runway API: No task ID in response")

        # Poll for result
        for _ in range(30):
            status_resp = requests.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers=headers,
                timeout=30
            ).json()

            status = status_resp.get("status", "")
            if status == "SUCCEEDED":
                output = status_resp.get("output", [])
                if output:
                    return output[0]
                raise Exception("Runway: No output URL")
            elif status == "FAILED":
                raise Exception(f"Runway failed: {status_resp.get('error', 'Unknown')}")

            time.sleep(10)

        raise TimeoutError("Runway video generation timed out")
