import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_TELEGRAM_BOT_TOKEN"
    DATABASE_URL: str = "sqlite+aiosqlite:///./video_editor.db"
    TEMP_STORAGE_PATH: str = "./temp_storage"
    WHISPER_MODEL: str = "base"

    # Video settings
    TARGET_WIDTH: int = 1080
    TARGET_HEIGHT: int = 1920
    TARGET_FPS: int = 30

    # Admin settings
    ADMIN_API_KEY: str = "admin_secret_key"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Ensure temp storage exists
os.makedirs(settings.TEMP_STORAGE_PATH, exist_ok=True)
