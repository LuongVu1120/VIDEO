import os
import secrets
import warnings
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


# Tim .env tu project root -> backend folder
def _find_env() -> str:
    candidates = [
        Path(__file__).parent.parent.parent.parent / ".env",  # project root
        Path(__file__).parent.parent.parent / ".env",         # backend folder
    ]
    for p in candidates:
        if p.exists():
            return str(p.absolute())
    return ".env"  # fallback


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Architecture Video Generator"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    AI_PROVIDER: str = "claude"  # claude | openai | deepseek

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/archvideo"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://user:password@localhost:5432/archvideo"
    FORCE_POSTGRES: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str = "ap-southeast-1"

    # AI - Vision & Text
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # AI - DeepSeek V4
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # AI - Image Generation
    REPLICATE_API_TOKEN: Optional[str] = None

    # AI - Video Generation
    VIDEO_PROVIDER: str = "fal"  # fal | veo | runway | auto
    FAL_KEY: Optional[str] = None
    # Cheaper default: Kling 2.5 Turbo ~$0.21/5s vs O3 ~$0.42/5s (audio off)
    FAL_VIDEO_MODEL: str = "fal-ai/kling-video/v2.5-turbo/standard/image-to-video"
    FAL_VIDEO_DURATION: str = "5"
    FAL_VIDEO_GENERATE_AUDIO: bool = False
    FAL_VIDEO_TIMEOUT_SECONDS: int = 600
    # How many creative variations get a video (1 = half the old default of 2)
    VIDEO_MAX_VARIATIONS: int = 1
    # Ghép nhạc nền bằng FFmpeg sau khi tạo video (thư viện backend/bgm/)
    VIDEO_ADD_BGM: bool = True
    BGM_VOLUME: float = 0.22
    BGM_LIBRARY_DIR: str = ""  # empty = backend/bgm
    GOOGLE_API_KEY: Optional[str] = None  # Google Veo 3.1 (Gemini API)
    RUNWAY_API_KEY: Optional[str] = None  # Runway fallback

    # Use DeepSeek flags
    USE_DEEPSEEK_FOR_PROMPTS: bool = True
    USE_DEEPSEEK_FOR_CAPTIONS: bool = True

    # Ngôn ngữ nội dung: vi (ưu tiên tiếng Việt) | en
    CONTENT_LANGUAGE: str = "vi"
    # Caption đăng MXH: vi hoặc en (caption song ngữ vẫn tạo cả hai)
    CAPTION_POST_LANGUAGE: str = "vi"

    # Social Media
    BUFFER_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_USER_ID: Optional[str] = None
    TIKTOK_ACCESS_TOKEN: Optional[str] = None
    FACEBOOK_PAGE_ID: Optional[str] = None
    FACEBOOK_PAGE_ACCESS_TOKEN: Optional[str] = None
    YOUTUBE_CLIENT_SECRETS_FILE: str = "youtube_client_secret.json"
    YOUTUBE_TOKEN_FILE: str = "youtube_token.json"
    YOUTUBE_PRIVACY_STATUS: str = "private"  # private | unlisted | public
    YOUTUBE_CATEGORY_ID: str = "22"  # People & Blogs
    # URL công khai tới media (Instagram Graph API cần fetch được). Dev: http://127.0.0.1:8000 hoặc ngrok.
    PUBLIC_MEDIA_BASE_URL: str = "http://127.0.0.1:8000"

    # Branding / Watermark
    BRAND_NAME: str = ""            # Tên công ty / tên cá nhân
    BRAND_PHONE: str = ""           # Số điện thoại
    BRAND_WATERMARK_POSITION: str = "bottom-right"  # bottom-right | bottom-left | top-right | top-left

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_env(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value

    class Config:
        env_file = _find_env()
        case_sensitive = True
        extra = "ignore"  # Allow extra env vars (POSTGRES_PASSWORD, N8N_*, etc.)


settings = Settings()

# Security: warn if SECRET_KEY is still the default value
if settings.SECRET_KEY == "change-me-in-production":
    print("=" * 60)
    print("⚠️  SECURITY WARNING: SECRET_KEY is still the default value!")
    print("   Set SECRET_KEY in your .env file to a random string.")
    print(f"   Example: SECRET_KEY={secrets.token_hex(32)}")
    print("=" * 60)
