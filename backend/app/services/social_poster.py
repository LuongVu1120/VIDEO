"""Step 7: Social Media Poster - Auto-post to Reels/Shorts/TikTok.

Hien tai ho tro mock output. Can Buffer/Instagram/TikTok API token de active.
"""

import json
import requests
import base64
from ..core.config import settings


class SocialPoster:
    """Auto-post generated content to social media platforms."""

    def __init__(self):
        self.buffer_token = settings.BUFFER_ACCESS_TOKEN
        self.instagram_token = settings.INSTAGRAM_ACCESS_TOKEN
        self.tiktok_token = settings.TIKTOK_ACCESS_TOKEN

    def post_to_platform(self,
                        image_url: str,
                        video_url: str | None,
                        caption: dict,
                        platform: str = "instagram",
                        dry_run: bool = True) -> dict:
        """
        Post content to a social media platform.

        Args:
            image_url: URL of generated image
            video_url: URL of generated video (optional)
            caption: dict with title, caption, hashtags, call_to_action
            platform: "instagram" | "tiktok" | "youtube"
            dry_run: If True, just validate without actually posting

        Returns:
            dict with status, post_url (if successful), or error details
        """
        if dry_run:
            return self._dry_run(platform, image_url, video_url, caption)

        posters = {
            "instagram": self._post_instagram,
            "tiktok": self._post_tiktok,
            "youtube": self._post_youtube_shorts,
        }

        poster = posters.get(platform)
        if not poster:
            return {"status": "error", "error": f"Unsupported platform: {platform}"}

        return poster(image_url, video_url, caption)

    def post_to_all(self,
                   image_url: str,
                   video_url: str | None,
                   captions: dict,
                   dry_run: bool = True) -> dict:
        """Post to all configured platforms."""
        results = {}
        for platform in captions:
            if platform in ("instagram", "tiktok", "youtube"):
                results[platform] = self.post_to_platform(
                    image_url, video_url, captions[platform], platform, dry_run
                )
        return results

    # ==================== DRY RUN ====================

    def _dry_run(self, platform: str, image_url: str,
                 video_url: str | None, caption: dict) -> dict:
        """Validate without posting - for testing."""
        hashtags = caption.get("hashtags", [])
        caption_text = caption.get("caption", "")

        # Validate hashtag format
        invalid_tags = [t for t in hashtags if not t.startswith("#")]
        if invalid_tags:
            hashtags = [f"#{t}" if not t.startswith("#") else t for t in hashtags]

        # Build post preview
        full_caption = f"{caption_text}\n\n{' '.join(hashtags)}"
        if caption.get("call_to_action"):
            full_caption += f"\n\n{caption['call_to_action']}"

        print(f"\n[DRY RUN] === POST TO {platform.upper()} ===")
        print(f"  Title: {caption.get('title', 'N/A')}")
        print(f"  Media: {'image' if image_url else 'none'}" +
              (f" + video" if video_url else ""))
        print(f"  Caption length: {len(full_caption)} chars")
        print(f"  Hashtags: {len(hashtags)} tags")
        print(f"  CTA: {caption.get('call_to_action', 'none')}")
        print(f"[DRY RUN] ================================\n")

        return {
            "status": "dry_run_ok",
            "platform": platform,
            "media": {"image": bool(image_url), "video": bool(video_url)},
            "caption_preview": full_caption[:200] + "..." if len(full_caption) > 200 else full_caption,
            "hashtag_count": len(hashtags),
            "post_url": None,
            "note": "Dry run - no actual post made. Set dry_run=False to post."
        }

    # ==================== INSTAGRAM ====================

    def _post_instagram(self, image_url: str, video_url: str | None,
                        caption: dict) -> dict:
        """Post to Instagram Reels/Feed using Graph API."""
        token = self.instagram_token
        if not token:
            return {"status": "error", "error": "Instagram token not configured"}

        hashtags = caption.get("hashtags", [])
        caption_text = caption.get("caption", "")
        formatted_caption = f"{caption_text}\n\n{' '.join(hashtags)}"

        if video_url:
            # Instagram Reel
            return self._post_instagram_reel(video_url, formatted_caption, token)
        else:
            # Instagram Feed (carousel or single image)
            return self._post_instagram_feed(image_url, formatted_caption, token)

    def _post_instagram_reel(self, video_url: str, caption: str, token: str) -> dict:
        """Post Reel to Instagram."""
        # Instagram Graph API: POST /{ig-user-id}/media
        # Params: media_type=REELS, video_url=..., caption=...
        ig_user_id = ""  # Need to get from API or config
        url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media"

        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        }

        try:
            resp = requests.post(url, data=payload, timeout=30)
            result = resp.json()

            if "id" in result:
                # Then publish
                creation_id = result["id"]
                publish_url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish"
                publish_resp = requests.post(publish_url, data={
                    "creation_id": creation_id,
                    "access_token": token,
                }, timeout=30)
                return {"status": "posted", "post_url": f"https://instagram.com/p/{creation_id}"}
            else:
                return {"status": "error", "error": str(result)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _post_instagram_feed(self, image_url: str, caption: str, token: str) -> dict:
        """Post image to Instagram Feed."""
        ig_user_id = ""  # Need from config/API
        url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media"

        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": token,
        }

        try:
            resp = requests.post(url, data=payload, timeout=30)
            result = resp.json()
            if "id" in result:
                return {"status": "posted", "post_url": f"https://instagram.com/p/{result['id']}"}
            return {"status": "error", "error": str(result)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ==================== TIKTOK ====================

    def _post_tiktok(self, image_url: str, video_url: str | None,
                     caption: dict) -> dict:
        """Post to TikTok using their API."""
        token = self.tiktok_token
        if not token:
            return {"status": "error", "error": "TikTok token not configured"}

        if not video_url:
            return {"status": "error", "error": "TikTok requires video content"}

        hashtags = caption.get("hashtags", [])
        caption_text = caption.get("caption", "")
        formatted_caption = f"{caption_text}\n\n{' '.join(hashtags)}"

        # TikTok Content Posting API
        url = "https://open-api.tiktok.com/share/video/upload/"

        payload = {
            "access_token": token,
            "video_url": video_url,
            "caption": formatted_caption[:2200],  # TikTok limit
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            result = resp.json()
            if result.get("data", {}).get("error_code") == 0:
                share_id = result["data"]["share_id"]
                return {"status": "posted", "post_url": f"https://tiktok.com/@user/video/{share_id}"}
            return {"status": "error", "error": str(result)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ==================== YOUTUBE SHORTS ====================

    def _post_youtube_shorts(self, image_url: str, video_url: str | None,
                              caption: dict) -> dict:
        """Post to YouTube Shorts (requires OAuth)."""
        # YouTube Data API v3 requires OAuth 2.0 with refresh token
        # This is more complex - typically needs youtube.upload scope
        return {
            "status": "not_implemented",
            "error": "YouTube Shorts API requires OAuth 2.0 setup. "
                     "See: https://developers.google.com/youtube/v3/guides/uploading_a_video",
            "title": caption.get("title", "Architecture Design"),
            "description": caption.get("caption", ""),
            "tags": caption.get("hashtags", []),
        }
