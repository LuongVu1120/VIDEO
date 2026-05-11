"""Step 7: Social Media Poster — Auto-post to Instagram, TikTok, YouTube, Facebook.

Caption format accepted (bilingual or flat):
  bilingual: {"vi": {"title":..., "caption":..., "hashtags":[], "call_to_action":...},
               "en": {...}}
  flat:       {"title":..., "caption":..., "hashtags":[], "call_to_action":...}
"""

import requests
from ..core.config import settings


# All platforms post in English. Vietnamese ("vi") is only shown in UI for user reference.
PLATFORM_LANG = {
    "instagram": "en",
    "tiktok":    "en",
    "facebook":  "en",
    "youtube":   "en",
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
            lang = PLATFORM_LANG.get(platform, "vi")
            return caption_data.get(lang) or caption_data.get("vi") or caption_data.get("en") or {}
        return caption_data

    def _format_caption(self, caption: dict) -> str:
        text = caption.get("caption", "")
        hashtags = caption.get("hashtags", [])
        cta = caption.get("call_to_action", "")
        parts = [text]
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
        base = f"https://graph.facebook.com/v21.0/{user_id}"
        try:
            r = requests.post(f"{base}/media", data={
                "media_type": "REELS", "video_url": video_url,
                "caption": caption, "access_token": token,
            }, timeout=30)
            data = r.json()
            if "id" not in data:
                return {"status": "error", "error": str(data)}
            r2 = requests.post(f"{base}/media_publish", data={
                "creation_id": data["id"], "access_token": token,
            }, timeout=30)
            result = r2.json()
            return {"status": "posted", "post_url": f"https://instagram.com/reel/{result.get('id', '')}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _ig_feed(self, user_id, image_url, caption, token) -> dict:
        base = f"https://graph.facebook.com/v21.0/{user_id}"
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
            return {"status": "posted", "post_url": f"https://instagram.com/p/{result.get('id', '')}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

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
        return {
            "status": "not_implemented",
            "note": "YouTube Shorts requires OAuth 2.0. "
                    "See: https://developers.google.com/youtube/v3/guides/uploading_a_video",
            "title": caption.get("title", ""),
            "description": caption.get("caption", ""),
            "tags": caption.get("hashtags", []),
        }

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

