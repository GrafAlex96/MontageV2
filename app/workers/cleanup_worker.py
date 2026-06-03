import os
import time
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def cleanup_old_files(max_age_seconds: int = 86400): # 24 hours
    """Cleanup files older than max_age_seconds in temp storage."""
    now = time.time()
    count = 0
    bytes_freed = 0

    for filename in os.listdir(settings.TEMP_STORAGE_PATH):
        filepath = os.path.join(settings.TEMP_STORAGE_PATH, filename)
        try:
            if os.path.isfile(filepath):
                if now - os.path.getmtime(filepath) > max_age_seconds:
                    bytes_freed += os.path.getsize(filepath)
                    os.remove(filepath)
                    count += 1
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {e}")

    if count > 0:
        logger.info(f"Cleanup worker: Removed {count} files, freed {bytes_freed / 1024 / 1024:.2f} MB")

async def run_cleanup_loop():
    while True:
        await cleanup_old_files()
        import asyncio
        await asyncio.sleep(3600) # Run every hour
