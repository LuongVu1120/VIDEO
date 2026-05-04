import os
from pathlib import Path
from pydantic_settings import BaseSettings
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
    GOOGLE_API_KEY: Optional[str] = None  # Google Veo 3.1 (Gemini API)
    RUNWAY_API_KEY: Optional[str] = None  # Runway fallback

    # Use DeepSeek flags
    USE_DEEPSEEK_FOR_PROMPTS: bool = True
    USE_DEEPSEEK_FOR_CAPTIONS: bool = True

    # Social Media
    BUFFER_ACCESS_TOKEN: Optional[str] = None
    INSTAGRAM_ACCESS_TOKEN: Optional[str] = None
    TIKTOK_ACCESS_TOKEN: Optional[str] = None

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = _find_env()
        case_sensitive = True


settings = Settings()
