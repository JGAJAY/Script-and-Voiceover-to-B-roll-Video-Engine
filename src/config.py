import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union

class Settings(BaseSettings):
    # App
    APP_NAME: str = "IncuBrix B-Roll Video Engine"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "production"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on", "debug")
        return bool(v)
    
    # Storage
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage")
    BASE_URL: str = "http://localhost:8000"
    
    # S3 / MinIO Settings
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "incubrix-videos"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    
    # Security & Idempotency
    WEBHOOK_SECRET: str = "incubrix-super-secret-hmac-key"
    MAX_CONCURRENT_JOBS: int = 4
    
    # Video & Processing Constraints
    MAX_AUDIO_DURATION_SECONDS: float = 600.0  # 10 minutes
    MIN_SCENE_DURATION_SECONDS: float = 2.0   # Enforce sensible pacing
    MAX_SCENE_DURATION_SECONDS: float = 6.5
    DEFAULT_ASPECT_RATIOS: List[str] = ["16:9", "9:16"]
    DEFAULT_VOICE: str = "en-IN-female"
    
    # External APIs (Optional - mock fallbacks automatically active if missing)
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ENABLE_MOCK_SOURCES: bool = True
    
    # FFmpeg executable path
    FFMPEG_PATH: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()

# Ensure directories exist
Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.STORAGE_DIR, "uploads").mkdir(parents=True, exist_ok=True)
Path(settings.STORAGE_DIR, "outputs").mkdir(parents=True, exist_ok=True)
Path(settings.STORAGE_DIR, "cache").mkdir(parents=True, exist_ok=True)
Path(settings.STORAGE_DIR, "clips").mkdir(parents=True, exist_ok=True)
