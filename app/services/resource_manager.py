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
        """Returns RAM used by the CURRENT process and its children in MB."""
        process = psutil.Process(os.getpid())
        mem_bytes = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                mem_bytes += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return mem_bytes / (1024 * 1024)

    @staticmethod
    def get_system_memory_usage_pct() -> float:
        """Returns total system RAM usage percentage."""
        return psutil.virtual_memory().percent

    @staticmethod
    def safe_mode_decision(limit_mb: int) -> dict:
        """
        Determine the allowed pipeline complexity based on current RAM state.
        Returns a policy dictionary.
        """
        # We use a hybrid approach: check both process-specific MB and system-wide %
        used_mb = ResourceManager.get_memory_used_mb()
        system_pct = ResourceManager.get_system_memory_usage_pct()

        # Budget-based percentage (if we have a hard limit)
        budget_pct = (used_mb / limit_mb) * 100 if limit_mb > 0 else 0

        # Effective pressure is the maximum of budget exhaustion or system-wide pressure
        effective_pct = max(budget_pct, system_pct)

        # Policy Tiers
        if effective_pct < 70:
            return {
                "mode": "FULL",
                "frame_skip": 5,
                "max_width": 720,
                "analyze_movement": True,
                "analyze_audio": True,
                "cap_frames": 1000
            }
        elif 70 <= effective_pct < 85:
            return {
                "mode": "REDUCED",
                "frame_skip": 15,
                "max_width": 480,
                "analyze_movement": True,
                "analyze_audio": True,
                "cap_frames": 500
            }
        elif 85 <= effective_pct < 92:
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
    def cleanup_zombie_processes(max_age_seconds: int = 600):
        """
        Find and terminate orphan or hung ffmpeg/magick processes.
        Kills processes older than max_age_seconds or in ZOMBIE status.
        """
        import time
        current_time = time.time()
        for proc in psutil.process_iter(['pid', 'name', 'create_time', 'status']):
            try:
                # Target our processing tools
                if proc.info['name'] in ['ffmpeg', 'ffprobe', 'magick', 'convert']:
                    # 1. Kill zombies immediately
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        logger.warning(f"Killing zombie process: {proc.info}")
                        # Zombie process cannot be killed by terminate, but its parent should reap it.
                        # However, in our environment we often have orphans.
                        # We try to kill it to ensure it's removed.
                        proc.kill()
                        continue

                    # 2. Kill hung processes older than threshold
                    age = current_time - proc.info['create_time']
                    if age > max_age_seconds:
                        logger.warning(f"Killing hung process (age {age:.1f}s): {proc.info}")
                        proc.kill()

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
        mem = ResourceManager.get_system_memory_usage_pct()

        if cpu > 95:
            logger.error(f"System CPU critical ({cpu}%). Stopping task.")
            raise RuntimeError("CPU limit exceeded")

        if mem > 94: # Slightly higher threshold for hard stop
            logger.error(f"System Memory critical ({mem}%). Stopping task.")
            raise RuntimeError("Memory limit exceeded")
