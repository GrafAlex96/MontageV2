import os
import subprocess
import json
from typing import Dict, Any

class FinalValidator:
    @staticmethod
    def validate_output(filepath: str, expected_duration: int) -> Dict[str, Any]:
        """Verify the final rendered file properties."""
        if not os.path.exists(filepath):
            return {"valid": False, "error": "File does not exist"}

        # 1. Use ffprobe to check duration and resolution
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', '-show_format', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        if not video_stream:
            return {"valid": False, "error": "No video stream found"}

        actual_duration = float(data['format']['duration'])
        width = int(video_stream['width'])
        height = int(video_stream['height'])

        # 2. Tolerance for duration (+/- 2 seconds)
        if abs(actual_duration - expected_duration) > 2.0:
             return {"valid": False, "error": f"Duration mismatch: {actual_duration}s vs {expected_duration}s"}

        # 3. Check resolution (1080x1920)
        if width != 1080 or height != 1920:
             return {"valid": False, "error": f"Resolution mismatch: {width}x{height}"}

        return {"valid": True, "duration": actual_duration, "resolution": f"{width}x{height}"}
