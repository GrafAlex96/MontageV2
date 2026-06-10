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
    def get_memory_used_mb() -> float:
        return psutil.virtual_memory().used / (1024 * 1024)

    @staticmethod
    def get_memory_status(limit_mb: int) -> str:
        """Return 'HEALTHY', 'SOFT_LIMIT', or 'HARD_LIMIT'."""
        used_mb = ResourceManager.get_memory_used_mb()
        if used_mb >= limit_mb:
            return "HARD_LIMIT"
        if used_mb >= 0.7 * limit_mb:
            return "SOFT_LIMIT"
        return "HEALTHY"

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
    def check_stage_budget(stage_name: str, memory_limit_mb: int = 1500):
        """Hard stage budget enforcement."""
        import gc
        gc.collect() # Force cleanup before check

        mem_info = psutil.virtual_memory()
        used_mb = mem_info.used / (1024 * 1024)

        if used_mb > memory_limit_mb:
            logger.critical(f"STAGE BUDGET EXCEEDED: {stage_name} using {used_mb}MB (Limit: {memory_limit_mb}MB)")
            raise RuntimeError(f"Memory budget exceeded in {stage_name}")

    @staticmethod
    def limit_resources():
        """Set global process limits for the current worker."""
        cpu = ResourceManager.get_cpu_usage()
        mem = ResourceManager.get_memory_usage()

        if cpu > 95:
            logger.error(f"System CPU critical ({cpu}%). Stopping task.")
            raise RuntimeError("CPU limit exceeded")

        if mem > 90:
            logger.error(f"System Memory critical ({mem}%). Stopping task.")
            raise RuntimeError("Memory limit exceeded")
