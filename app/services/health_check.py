import subprocess
import os
import logging
import sys
from redis import Redis
from sqlalchemy import create_engine
from app.core.config import settings

logger = logging.getLogger(__name__)

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_imagemagick():
    try:
        # MoviePy 2.x often needs 'magick' or 'convert'
        subprocess.run(['magick', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(['convert', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

def check_ffprobe():
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_redis():
    try:
        r = Redis.from_url(settings.REDIS_URL)
        return r.ping()
    except Exception:
        return False

def check_db():
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            return True
    except Exception:
        return False

def run_all_checks():
    print("🚀 Starting AI Video Editor Health Check...")

    checks = {
        "FFmpeg": check_ffmpeg(),
        "FFprobe": check_ffprobe(),
        "ImageMagick": check_imagemagick(),
        "Redis": check_redis(),
        "Database": check_db(),
        "Env (Bot Token)": bool(settings.BOT_TOKEN and settings.BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN"),
        "Temp Storage": os.access(settings.TEMP_STORAGE_PATH, os.W_OK)
    }

    all_pass = True
    for name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        if not result:
            all_pass = False
        print(f"{name:20}: {status}")

    if not all_pass:
        print("\n❌ SOME CHECKS FAILED. PLEASE FIX THEM BEFORE STARTING.")
        return False

    print("\n✅ ALL SYSTEMS GO.")
    return True

if __name__ == "__main__":
    if not run_all_checks():
        sys.exit(1)
