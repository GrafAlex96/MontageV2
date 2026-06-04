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

        # 4. Check for Audio Stream
        if not next((s for s in data['streams'] if s['codec_type'] == 'audio'), None):
            return {"valid": False, "error": "No audio stream found in final output"}

        # 5. Check for frame corruption (Silent Corruption check)
        # We check if frame count is reasonable for duration
        fps_str = video_stream.get('avg_frame_rate', '30/1')
        fps = eval(fps_str) if '/' in fps_str else float(fps_str)
        expected_frames = int(actual_duration * fps)
        actual_frames = int(video_stream.get('nb_frames', 0))

        if actual_frames > 0 and abs(actual_frames - expected_frames) > fps * 2: # 2 second tolerance
            return {"valid": False, "error": f"Frame count integrity failure: {actual_frames} vs {expected_frames}"}

        # 6. Check for Audio-Video Sync (Duration mismatch between streams)
        audio_stream = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
        if audio_stream:
            audio_duration = float(audio_stream.get('duration', actual_duration))
            if abs(audio_duration - actual_duration) > 1.0: # Increased tolerance for variable bitrates
                return {"valid": False, "error": f"Audio-Video desync detected: {audio_duration}s audio vs {actual_duration}s video"}

        return {"valid": True, "duration": actual_duration, "resolution": f"{width}x{height}"}
