import subprocess
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AudioService:
    def normalize_audio(self, input_path: str, output_path: str):
        """Normalize audio levels using ffmpeg-normalize or loudnorm filter."""
        # Using loudnorm filter for EBU R128 loudness normalization
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
            '-c:v', 'copy', # keep video stream
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def detect_beats(self, input_path: str) -> Dict[str, Any]:
        """Detect beats and return with confidence score."""
        import librosa
        import numpy as np
        from app.core.config import settings

        try:
            # Safe mode: reduced sampling for large files
            sr_target = 22050 if settings.SAFE_MODE else None
            y, sr = librosa.load(input_path, sr=sr_target)

            # 1. Energy check
            max_amp = np.max(np.abs(y))
            if max_amp < 0.02:
                return {"beats": [], "confidence": 0.0}

            # 2. Beat track
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            # 3. Simple Confidence Heuristic
            # If tempo is stable and in musical range
            confidence = 0.0

            # librosa.beat.beat_track returns a single float or an array depending on version/input
            tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0])

            if 60 <= tempo_val <= 180:
                confidence = 0.8
            elif 40 <= tempo_val <= 220:
                confidence = 0.5

            # Deduct if audio is very noisy or has low rhythmic peaks
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            # Ensure onset_env is not empty
            if len(onset_env) > 0:
                pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
                if np.mean(pulse) < 0.1:
                    confidence *= 0.5

            return {
                "beats": [float(t) for t in beat_times],
                "confidence": confidence,
                "tempo": tempo_val
            }
        except Exception as e:
            logger.warning(f"Beat detection failed: {e}")
            return {"beats": [], "confidence": 0.0}

    def remove_noise(self, input_path: str, output_path: str):
        """Apply noise reduction using afftdn filter."""
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-af', 'afftdn=nf=-25',
            '-c:v', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def improve_clarity(self, input_path: str, output_path: str):
        """Combine normalization, noise reduction and equalization."""
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-af', 'afftdn=nf=-25,equalizer=f=3000:width_type=h:w=200:g=3,loudnorm=I=-16',
            '-c:v', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
