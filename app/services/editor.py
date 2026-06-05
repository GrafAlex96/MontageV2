import asyncio
import subprocess
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def process_video_ffmpeg(input_path: str, output_path: str, duration: int = 15) -> bool:
    """
    Run basic FFmpeg editing in a separate thread.
    Scales to 1080x1920 (9:16) and trims to duration.
    """
    # Placeholder for actual complex logic
    # Basic command: Scale, pad, and trim
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', f'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1',
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
        output_path
    ]

    try:
        # Run in executor to avoid blocking the event loop
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return True
        else:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            return False
    except Exception as e:
        logger.error(f"Failed to run FFmpeg: {e}")
        return False

class Editor:
    def __init__(self, target_duration: int = 15):
        self.target_duration = target_duration

    def select_best_segments(self, scenes: list) -> list:
        """Select top scenes that fit within target duration."""
        sorted_scenes = sorted(scenes, key=lambda x: x.score, reverse=True)
        selected = []
        current_duration = 0

        from dataclasses import replace
        for scene in sorted_scenes:
            scene_duration = scene.end_time - scene.start_time
            if current_duration + scene_duration <= self.target_duration:
                selected.append(scene)
                current_duration += scene_duration
            elif current_duration < self.target_duration:
                # Add partial segment if there's space
                remaining = self.target_duration - current_duration
                if remaining > 0.1:
                    trimmed_scene = replace(scene, end_time=scene.start_time + remaining)
                    selected.append(trimmed_scene)
                    current_duration += remaining
                    break
        return selected
