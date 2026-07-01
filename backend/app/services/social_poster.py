"""Step 7: Social Media Poster — Auto-post to Instagram, TikTok, YouTube, Facebook.

Caption format accepted (bilingual or flat):
  bilingual: {"vi": {"title":..., "caption":..., "hashtags":[], "call_to_action":...},
               "en": {...}}
  flat:       {"title":..., "caption":..., "hashtags":[], "call_to_action":...}
"""

import requests
import mimetypes
import os
import time
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from ..core.config import settings
from .caption_utils import MAX_POST_CAPTION_WORDS, limit_caption_words


def _platform_post_lang() -> dict[str, str]:
    """Ngôn ngữ caption khi đăng bài — mặc định theo CAPTION_POST_LANGUAGE."""
    post = (settings.CAPTION_POST_LANGUAGE or "vi").lower()
    if post.startswith("vi"):
        return {
            "instagram": "vi",
            "tiktok": "vi",
            "facebook": "vi",
            "youtube": "vi",
        }
    return {
        "instagram": "en",
        "tiktok": "en",
        "facebook": "en",
        "youtube": "en",
    }


class SocialPoster:

    def __init__(self):
        self.instagram_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.tiktok_token    = settings.TIKTOK_ACCESS_TOKEN
        self.buffer_token    = settings.BUFFER_ACCESS_TOKEN
        self.fb_page_id      = settings.FACEBOOK_PAGE_ID
        self.fb_page_token   = settings.FACEBOOK_PAGE_ACCESS_TOKEN

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_to_platform(
        self,
        image_url: str,
        video_url: str | None,
        caption_data: dict,
        platform: str = "instagram",
        dry_run: bool = True,
    ) -> dict:
        caption = self._extract_caption(caption_data, platform)

        if dry_run:
            return self._dry_run(platform, image_url, video_url, caption)

        posters = {
            "instagram": self._post_instagram,
            "tiktok":    self._post_tiktok,
            "youtube":   self._post_youtube_shorts,
            "facebook":  self._post_facebook,
        }
        poster = posters.get(platform)
        if not poster:
            return {"status": "error", "error": f"Unsupported platform: {platform}"}
        return poster(image_url, video_url, caption)

    def post_to_all(
        self,
        image_url: str,
        video_url: str | None,
        captions: dict,
        dry_run: bool = True,
    ) -> dict:
        """Post to every platform present in captions dict."""
        supported = {"instagram", "tiktok", "youtube", "facebook"}
        results = {}
        for platform in captions:
            if platform in supported:
                results[platform] = self.post_to_platform(
                    image_url, video_url, captions[platform], platform, dry_run
                )
        return results

    # ------------------------------------------------------------------
    # Caption extraction (handles bilingual or flat dict)
    # ------------------------------------------------------------------

    def _extract_caption(self, caption_data: dict, platform: str) -> dict:
        """
        If caption_data is bilingual {"vi": {...}, "en": {...}},
        pick the language appropriate for the platform.
        Otherwise return as-is.
        """
        if not isinstance(caption_data, dict):
            return {}
        if "vi" in caption_data or "en" in caption_data:
            lang = _platform_post_lang().get(platform, "vi")
            return caption_data.get(lang) or caption_data.get("vi") or caption_data.get("en") or {}
        return caption_data

    def _format_caption(self, caption: dict) -> str:
        text = limit_caption_words(caption.get("caption", ""), MAX_POST_CAPTION_WORDS)
        hashtags = caption.get("hashtags", [])
        cta = limit_caption_words(caption.get("call_to_action", ""), MAX_POST_CAPTION_WORDS)
        parts = [text] if text else []
        if hashtags:
            parts.append("\n" + " ".join(
                t if t.startswith("#") else f"#{t}" for t in hashtags
            ))
        if cta:
            parts.append(f"\n{cta}")
        return "".join(parts)

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def _dry_run(self, platform: str, image_url: str,
                 video_url: str | None, caption: dict) -> dict:
        full = self._format_caption(caption)
        hashtags = caption.get("hashtags", [])
        print(f"\n[DRY RUN] === POST TO {platform.upper()} ===")
        print(f"  Title          : {caption.get('title', 'N/A')}")
        print(f"  Media          : {'image' if image_url else 'none'}"
              + (" + video" if video_url else ""))
        print(f"  Caption length : {len(full)} chars")
        print(f"  Hashtags       : {len(hashtags)}")
        print(f"  CTA            : {caption.get('call_to_action', 'none')}")
        print(f"[DRY RUN] ===========================\n")
        return {
            "status": "dry_run_ok",
            "platform": platform,
            "media": {"image": bool(image_url), "video": bool(video_url)},
            "caption_preview": full[:200] + ("..." if len(full) > 200 else ""),
            "hashtag_count": len(hashtags),
            "post_url": None,
            "note": "Dry run — no actual post. Set dry_run=False to publish.",
        }

    # ------------------------------------------------------------------
    # Instagram (Graph API v21)
    # ------------------------------------------------------------------

    def _instagram_graph_host(self, token: str) -> str:
        # Instagram Login tokens use the Instagram Graph host; Facebook Login tokens use Facebook Graph.
        return "https://graph.instagram.com" if token.startswith("IGA") else "https://graph.facebook.com"

    def _instagram_user_base(self, user_id: str, token: str) -> str:
        return f"{self._instagram_graph_host(token)}/v21.0/{user_id}"

    def _post_instagram(self, image_url, video_url, caption) -> dict:
        token = self.instagram_token
        if not token:
            return {"status": "error", "error": "Instagram token not configured"}

        ig_user_id = settings.INSTAGRAM_USER_ID or ""
        if not ig_user_id:
            return {"status": "error", "error": "INSTAGRAM_USER_ID not configured"}

        formatted = self._format_caption(caption)

        if video_url:
            return self._ig_reel(ig_user_id, video_url, formatted, token)
        return self._ig_feed(ig_user_id, image_url, formatted, token)

    def _ig_reel(self, user_id, video_url, caption, token) -> dict:
        base = self._instagram_user_base(user_id, token)
        try:
            r = requests.post(f"{base}/media", data={
                "media_type": "REELS", "video_url": video_url,
                "caption": caption, "share_to_feed": "true", "access_token": token,
            }, timeout=30)
            data = r.json()
            if "id" not in data:
                return {"status": "error", "error": str(data)}
            ready = self._wait_for_instagram_container(data["id"], token)
            if ready.get("status") != "ready":
                return {"status": "error", "error": str(ready)}
            r2 = requests.post(f"{base}/media_publish", data={
                "creation_id": data["id"], "access_token": token,
            }, timeout=30)
            result = r2.json()
            if "id" not in result:
                return {"status": "error", "error": str(result)}
            return {
                "status": "posted",
                "media_id": result["id"],
                "post_url": self._get_instagram_permalink(result["id"], token),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _ig_feed(self, user_id, image_url, caption, token) -> dict:
        base = self._instagram_user_base(user_id, token)
        try:
            r = requests.post(f"{base}/media", data={
                "image_url": image_url, "caption": caption, "access_token": token,
            }, timeout=30)
            data = r.json()
            if "id" not in data:
                return {"status": "error", "error": str(data)}
            r2 = requests.post(f"{base}/media_publish", data={
                "creation_id": data["id"], "access_token": token,
            }, timeout=30)
            result = r2.json()
            if "id" not in result:
                return {"status": "error", "error": str(result)}
            return {
                "status": "posted",
                "media_id": result["id"],
                "post_url": self._get_instagram_permalink(result["id"], token),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _wait_for_instagram_container(self, container_id: str, token: str) -> dict:
        url = f"{self._instagram_graph_host(token)}/v21.0/{container_id}"
        for _ in range(30):
            r = requests.get(
                url,
                params={"fields": "status_code", "access_token": token},
                timeout=15,
            )
            data = r.json()
            status = data.get("status_code")
            if status == "FINISHED":
                return {"status": "ready"}
            if status in {"ERROR", "EXPIRED"}:
                return {"status": "error", "container_status": status, "details": data}
            time.sleep(10)
        return {"status": "timeout", "error": "Instagram media container was not ready in time"}

    def _get_instagram_permalink(self, media_id: str, token: str) -> str:
        try:
            r = requests.get(
                f"{self._instagram_graph_host(token)}/v21.0/{media_id}",
                params={"fields": "permalink", "access_token": token},
                timeout=15,
            )
            data = r.json()
            return data.get("permalink") or f"https://instagram.com/p/{media_id}"
        except Exception:
            return f"https://instagram.com/p/{media_id}"

    # ------------------------------------------------------------------
    # TikTok
    # ------------------------------------------------------------------

    def _post_tiktok(self, image_url, video_url, caption) -> dict:
        token = self.tiktok_token
        if not token:
            return {"status": "error", "error": "TikTok token not configured"}
        if not video_url:
            return {"status": "error", "error": "TikTok requires video content"}

        formatted = self._format_caption(caption)
        try:
            r = requests.post(
                "https://open-api.tiktok.com/share/video/upload/",
                json={"access_token": token, "video_url": video_url,
                      "caption": formatted[:2200]},
                timeout=60,
            )
            data = r.json()
            share_id = data.get("data", {}).get("share_id", "")
            if data.get("data", {}).get("error_code") == 0:
                return {"status": "posted", "post_url": f"https://tiktok.com/@user/video/{share_id}"}
            return {"status": "error", "error": str(data)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # YouTube Shorts
    # ------------------------------------------------------------------

    def _post_youtube_shorts(self, image_url, video_url, caption) -> dict:
        if not video_url:
            return {"status": "error", "error": "YouTube requires video content"}

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as e:
            return {
                "status": "error",
                "error": (
                    "YouTube dependencies are missing. Install backend requirements "
                    f"again. Details: {e}"
                ),
            }

        token_path = self._resolve_config_path(settings.YOUTUBE_TOKEN_FILE)
        secrets_path = self._resolve_config_path(settings.YOUTUBE_CLIENT_SECRETS_FILE)
        if not token_path.exists():
            return {
                "status": "error",
                "error": (
                    f"YouTube OAuth token not found: {token_path}. "
                    "Run backend/scripts/youtube_oauth_setup.py once."
                ),
            }
        if not secrets_path.exists():
            return {
                "status": "error",
                "error": f"YouTube OAuth client secret not found: {secrets_path}",
            }

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
            if not creds.valid:
                return {
                    "status": "error",
                    "error": "YouTube OAuth token is invalid. Re-run youtube_oauth_setup.py.",
                }

            local_video, cleanup = self._prepare_youtube_video_file(video_url)
            try:
                formatted = self._format_caption(caption)
                raw_title = (caption.get("title") or "Architecture video")
                # Ensure YouTube classifies this as a Short (vertical ≤60s)
                title = (raw_title if "#Shorts" in raw_title else f"{raw_title} #Shorts")[:100]
                tags = [
                    str(tag).lstrip("#")
                    for tag in caption.get("hashtags", [])
                    if str(tag).strip()
                ]
                if "Shorts" not in tags:
                    tags.append("Shorts")
                tags = tags[:30]
                description = f"{formatted}\n\n#Shorts" if "#Shorts" not in formatted else formatted

                youtube = build("youtube", "v3", credentials=creds)
                media_type = mimetypes.guess_type(local_video)[0] or "video/mp4"
                request = youtube.videos().insert(
                    part="snippet,status",
                    body={
                        "snippet": {
                            "title": title,
                            "description": description,
                            "tags": tags,
                            "categoryId": settings.YOUTUBE_CATEGORY_ID,
                        },
                        "status": {
                            "privacyStatus": settings.YOUTUBE_PRIVACY_STATUS,
                            "selfDeclaredMadeForKids": False,
                        },
                    },
                    media_body=MediaFileUpload(
                        local_video,
                        mimetype=media_type,
                        chunksize=-1,
                        resumable=True,
                    ),
                )

                response = None
                while response is None:
                    _, response = request.next_chunk()
                video_id = response.get("id")
                if not video_id:
                    return {"status": "error", "error": str(response)}

                return {
                    "status": "posted",
                    "platform": "youtube",
                    "video_id": video_id,
                    "post_url": f"https://www.youtube.com/watch?v={video_id}",
                    "shorts_url": f"https://www.youtube.com/shorts/{video_id}",
                    "privacy_status": settings.YOUTUBE_PRIVACY_STATUS,
                }
            finally:
                if cleanup:
                    try:
                        os.remove(local_video)
                    except OSError:
                        pass
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _resolve_config_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[3] / path

    def _prepare_youtube_video_file(self, video_url: str) -> tuple[str, bool]:
        parsed = urlparse(video_url)
        if parsed.scheme in {"http", "https"}:
            suffix = Path(parsed.path).suffix or ".mp4"
            fd, temp_path = tempfile.mkstemp(prefix="youtube_upload_", suffix=suffix)
            os.close(fd)
            with requests.get(video_url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            return temp_path, True

        if parsed.scheme == "file":
            local_path = Path(parsed.path)
        else:
            local_path = Path(video_url)

        if not local_path.exists():
            raise FileNotFoundError(f"YouTube video file not found: {video_url}")
        return str(local_path), False

    # ------------------------------------------------------------------
    # Facebook Page (Graph API v21)
    # ------------------------------------------------------------------

    def _post_facebook(self, image_url, video_url, caption) -> dict:
        token = self.fb_page_token
        page_id = self.fb_page_id
        if not token:
            return {"status": "error", "error": "FACEBOOK_PAGE_ACCESS_TOKEN not configured"}
        if not page_id:
            return {"status": "error", "error": "FACEBOOK_PAGE_ID not configured"}

        formatted = self._format_caption(caption)
        title = caption.get("title", "")
        base = f"https://graph.facebook.com/v21.0/{page_id}"

        try:
            if video_url:
                # Upload video as Reel or video post
                r = requests.post(f"{base}/videos", data={
                    "file_url": video_url,
                    "title": title,
                    "description": formatted,
                    "access_token": token,
                }, timeout=60)
                data = r.json()
                if "id" in data:
                    return {
                        "status": "posted",
                        "post_url": f"https://facebook.com/{page_id}/videos/{data['id']}",
                    }
                return {"status": "error", "error": str(data)}

            elif image_url:
                # Post image to Page feed
                r = requests.post(f"{base}/photos", data={
                    "url": image_url,
                    "caption": formatted,
                    "access_token": token,
                }, timeout=30)
                data = r.json()
                if "id" in data:
                    post_id = data["id"]
                    return {
                        "status": "posted",
                        "post_url": f"https://facebook.com/{post_id}",
                    }
                return {"status": "error", "error": str(data)}

            else:
                return {"status": "error", "error": "No media provided for Facebook post"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

