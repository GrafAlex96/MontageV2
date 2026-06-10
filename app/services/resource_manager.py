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
    def safe_mode_decision(limit_mb: int) -> dict:
        """
        Determine the allowed pipeline complexity based on current RAM state.
        Returns a policy dictionary.
        """
        used_mb = ResourceManager.get_memory_used_mb()
        usage_pct = (used_mb / limit_mb) * 100 if limit_mb > 0 else 0

        # Policy Tiers
        if usage_pct < 70:
            return {
                "mode": "FULL",
                "frame_skip": 5,
                "max_width": 720,
                "analyze_movement": True,
                "analyze_audio": True,
                "cap_frames": 1000
            }
        elif 70 <= usage_pct < 85:
            return {
                "mode": "REDUCED",
                "frame_skip": 15,
                "max_width": 480,
                "analyze_movement": True,
                "analyze_audio": True,
                "cap_frames": 500
            }
        elif 85 <= usage_pct < 92:
            return {
                "mode": "ULTRA_SAFE",
                "frame_skip": 30,
                "max_width": 360,
                "analyze_movement": False,
                "analyze_audio": False,
                "cap_frames": 300
            }
        else:
            return {
                "mode": "MINIMAL",
                "frame_skip": 60,
                "max_width": 240,
                "analyze_movement": False,
                "analyze_audio": False,
                "cap_frames": 100
            }

    @staticmethod
    def get_memory_status(limit_mb: int) -> str:
        decision = ResourceManager.safe_mode_decision(limit_mb)
        return decision["mode"]

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
    def check_stage_budget(stage_name: str, memory_limit_mb: int = 1500) -> bool:
        """Hard stage budget enforcement with graceful fallback."""
        import gc
        gc.collect() # Force cleanup before check

        used_mb = ResourceManager.get_memory_used_mb()

        if used_mb > memory_limit_mb:
            logger.warning(f"STAGE BUDGET EXCEEDED: {stage_name} using {used_mb:.2f}MB (Limit: {memory_limit_mb}MB)")
            logger.warning("Switching to SAFE MODE fallback/degradation.")
            return False
        return True

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
