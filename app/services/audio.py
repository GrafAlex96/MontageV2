import subprocess
import os
from typing import List

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

    def detect_beats(self, input_path: str) -> List[float]:
        """Detect beats in the audio file using librosa."""
        import librosa
        try:
            y, sr = librosa.load(input_path, sr=None)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            return [float(t) for t in beat_times]
        except Exception as e:
            print(f"Beat detection failed: {e}")
            return []

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
