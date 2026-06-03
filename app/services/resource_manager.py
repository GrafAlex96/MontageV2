import psutil
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

class ResourceManager:
    @staticmethod
    def get_cpu_usage() -> float:
        return psutil.cpu_percent(interval=1)

    @staticmethod
    def get_memory_usage() -> float:
        return psutil.virtual_memory().percent

    @staticmethod
    def cleanup_zombie_processes():
        """Find and terminate orphan ffmpeg/magick processes."""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in ['ffmpeg', 'ffprobe', 'magick']:
                    # Check if process is old or has no parent
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        logger.info(f"Terminating zombie process: {proc.info}")
                        proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    @staticmethod
    def limit_resources():
        """Set process limits for the current worker."""
        # Simple implementation: log warning if system is overloaded
        if ResourceManager.get_cpu_usage() > 90:
            logger.warning("System CPU usage is extremely high!")
        if ResourceManager.get_memory_usage() > 90:
            logger.warning("System Memory usage is extremely high!")
