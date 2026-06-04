import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN"
    DATABASE_URL: str = "sqlite:///./video_editor.db"
    TEMP_STORAGE_PATH: str = "./uploads"
    WHISPER_MODEL: str = "base"

    # Video settings
    TARGET_WIDTH: int = 1080
    TARGET_HEIGHT: int = 1920
    TARGET_FPS: int = 30
    REDIS_URL: str = "redis://localhost:6379/0"

    # Admin settings
    ADMIN_API_KEY: str = "admin_secret_key"

    # SAFE MODE LIMITS
    MAX_VIDEO_SIZE_GB: float = 1.5
    MAX_CLIPS_PER_JOB: int = 3
    MAX_TOTAL_DURATION: int = 180

    # PERFORMANCE LIMITS
    MAX_CPU_PERCENT: float = 80.0
    MAX_RAM_MB: int = 2000
    RENDER_TIMEOUT: int = 120
    FFMPEG_KILL_TIMEOUT: int = 90

    # MODES
    SAFE_MODE: bool = True
    WHISPER_MODE: str = "auto"
    BEAT_SYNC_MODE: str = "adaptive"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Ensure temp storage exists
os.makedirs(settings.TEMP_STORAGE_PATH, exist_ok=True)
