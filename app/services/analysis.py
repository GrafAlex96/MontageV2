import cv2
import numpy as np
import os
from typing import List, Dict, Any
from dataclasses import dataclass
import subprocess
import json

@dataclass
class Scene:
    start_time: float
    end_time: float
    score: float = 0.0
    has_speech: bool = False
    movement_score: float = 0.0
    is_hook: bool = False
    is_peak: bool = False
    audio_energy: float = 0.0

class VideoAnalyzer:
    def __init__(self, video_path: str):
        self.video_path = video_path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

    def detect_scenes(self, threshold: float = 30.0) -> List[Scene]:
        """Detect scenes using color histogram changes."""
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30.0

        scenes = []
        prev_hist = None
        start_frame = 0
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Subsample frames for performance
            if frame_idx % 5 != 0:
                frame_idx += 1
                continue

            curr_hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
                if (1.0 - diff) * 100 > threshold:
                    scenes.append(Scene(start_frame / fps, frame_idx / fps))
                    start_frame = frame_idx

            prev_hist = curr_hist
            frame_idx += 1

        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        scenes.append(Scene(start_frame / fps, total_frames / fps))

        cap.release()
        return scenes

    def analyze_movement(self, scenes: List[Scene]) -> List[Scene]:
        """Analyze movement in each scene using optical flow or frame differencing."""
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        for scene in scenes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(scene.start_time * fps))
            ret, prev_frame = cap.read()
            if not ret: continue

            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            movements = []

            frames_to_check = int((scene.end_time - scene.start_time) * fps)
            # Check up to 30 frames per scene to save time
            step = max(1, frames_to_check // 30)

            for i in range(0, frames_to_check, step):
                ret, frame = cap.read()
                if not ret: break

                curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                flow = cv2.absdiff(prev_gray, curr_gray)
                movement = np.mean(flow)
                movements.append(movement)
                prev_gray = curr_gray

            scene.movement_score = float(np.mean(movements)) if movements else 0.0

        cap.release()
        return scenes

    def detect_silence(self) -> List[Dict[str, float]]:
        """Use FFmpeg to detect silent segments."""
        cmd = [
            'ffmpeg', '-i', self.video_path,
            '-af', 'silencedetect=noise=-30dB:d=0.5',
            '-f', 'null', '-'
        ]
        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        _, stderr = process.communicate()
        stderr = stderr.decode()

        silences = []
        for line in stderr.split('\n'):
            if 'silence_start' in line:
                start = float(line.split('silence_start: ')[1].split()[0])
                silences.append({'start': start})
            elif 'silence_end' in line:
                end = float(line.split('silence_end: ')[1].split('|')[0].strip())
                if silences:
                    silences[-1]['end'] = end
                    silences[-1]['duration'] = end - silences[-1]['start']

        return silences

    def analyze_audio_energy(self, scenes: List[Scene]) -> List[Scene]:
        """Analyze audio energy for each scene."""
        import librosa
        try:
            y, sr = librosa.load(self.video_path, sr=None)
            for scene in scenes:
                start_idx = int(scene.start_time * sr)
                end_idx = int(scene.end_time * sr)
                if start_idx < len(y):
                    segment = y[start_idx:min(end_idx, len(y))]
                    scene.audio_energy = float(np.mean(librosa.feature.rms(y=segment)))
        except Exception as e:
            print(f"Audio analysis failed: {e}")
        return scenes

    def detect_hooks_and_peaks(self, scenes: List[Scene]) -> List[Scene]:
        """Identify scenes that can serve as hooks or emotional peaks."""
        if not scenes: return scenes

        # Hooks: High movement OR high audio energy at the beginning
        # Peaks: Highest combined movement and audio energy

        for scene in scenes:
            combined_intensity = scene.movement_score * 0.5 + scene.audio_energy * 50.0
            if combined_intensity > 5.0: # Arbitrary threshold
                scene.is_peak = True

        # Sort by intensity to find the best hook
        sorted_by_intensity = sorted(scenes, key=lambda x: x.movement_score * 0.5 + x.audio_energy * 50.0, reverse=True)
        if sorted_by_intensity:
            sorted_by_intensity[0].is_hook = True

        return scenes

    def generate_quality_scores(self, scenes: List[Scene], silences: List[Dict[str, float]]) -> List[Scene]:
        """Generate quality scores for each scene based on movement, audio, and presence of silence."""
        for scene in scenes:
            # Base score from movement and audio
            score = min(scene.movement_score * 2.0 + scene.audio_energy * 100.0, 10.0)

            # Bonus for hooks and peaks
            if scene.is_hook: score += 2.0
            if scene.is_peak: score += 1.0

            # Penalize for overlapping with silence
            silence_penalty = 0
            for silence in silences:
                # Calculate overlap between scene [scene.start_time, scene.end_time]
                # and silence [silence['start'], silence['end']]
                silence_start = silence['start']
                silence_end = silence.get('end', scene.end_time)

                overlap_start = max(scene.start_time, silence_start)
                overlap_end = min(scene.end_time, silence_end)

                if overlap_start < overlap_end:
                    overlap_duration = overlap_end - overlap_start
                    scene_duration = scene.end_time - scene.start_time
                    if scene_duration > 0:
                        silence_penalty += (overlap_duration / scene_duration) * 5.0

            scene.score = max(0.0, score - silence_penalty)

        # Normalize scores to 0-10 range if needed, but here we just cap
        return sorted(scenes, key=lambda x: x.score, reverse=True)
