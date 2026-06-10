import cv2
import numpy as np
import os
from typing import List, Dict, Any
from dataclasses import dataclass
import subprocess
import json

@dataclass(frozen=True)
class Scene:
    start_time: float
    end_time: float
    score: float = 0.0
    has_speech: bool = False
    movement_score: float = 0.0
    is_hook: bool = False
    is_peak: bool = False
    audio_energy: float = 0.0
    source_video_id: str = "" # UUID or Path
    timeline_offset: float = 0.0

class VideoAnalyzer:
    def __init__(self, video_path: str, frame_skip: int = 5, max_width: int = 720):
        self.video_path = video_path
        self.frame_skip = frame_skip
        self.max_width = max_width
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

    def _downscale_frame(self, frame):
        """Downscale frame if it exceeds max_width."""
        h, w = frame.shape[:2]
        if w > self.max_width:
            scale = self.max_width / w
            new_w = self.max_width
            new_h = int(h * scale)
            return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return frame

    def get_frame_count(self) -> int:
        cap = cv2.VideoCapture(self.video_path)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return count

    def detect_scenes(self, threshold: float = 30.0) -> List[Scene]:
        """Detect scenes using color histogram changes with frame streaming and sampling."""
        import gc
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

            # Sampling strategy
            if frame_idx % self.frame_skip != 0:
                frame_idx += 1
                continue

            # Downscale for memory efficiency
            frame = self._downscale_frame(frame)

            curr_hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            curr_hist = cv2.normalize(curr_hist, curr_hist).flatten()

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, curr_hist, cv2.HISTCMP_CORREL)
                if (1.0 - diff) * 100 > threshold:
                    scenes.append(Scene(start_frame / fps, frame_idx / fps))
                    start_frame = frame_idx

            prev_hist = curr_hist
            frame_idx += 1

            # Explicit cleanup
            del frame
            if frame_idx % 100 == 0:
                gc.collect()

        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        scenes.append(Scene(start_frame / fps, total_frames / fps))

        cap.release()
        gc.collect()
        return scenes

    def analyze_movement(self, scenes: List[Scene]) -> List[Scene]:
        """Analyze movement using incremental frame differencing and streaming."""
        import gc
        from dataclasses import replace
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30.0

        updated_scenes = []
        for scene in scenes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(scene.start_time * fps))
            ret, prev_frame = cap.read()
            if not ret:
                updated_scenes.append(scene)
                continue

            prev_frame = self._downscale_frame(prev_frame)
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            del prev_frame

            movements = []
            frames_to_check = int((scene.end_time - scene.start_time) * fps)

            # Adaptive step: ensure we check at least 10 points but skip enough to save RAM
            step = max(self.frame_skip, frames_to_check // 20)

            for i in range(0, frames_to_check, step):
                ret, frame = cap.read()
                if not ret: break

                frame = self._downscale_frame(frame)
                curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                flow = cv2.absdiff(prev_gray, curr_gray)
                movement = np.mean(flow)
                movements.append(movement)

                prev_gray = curr_gray
                del frame
                del curr_gray

            score = float(np.mean(movements)) if movements else 0.0
            updated_scenes.append(replace(scene, movement_score=score))

            # Cleanup after each scene
            del prev_gray
            gc.collect()

        cap.release()
        gc.collect()
        return updated_scenes

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
        from dataclasses import replace
        updated_scenes = []
        try:
            y, sr = librosa.load(self.video_path, sr=None)
            for scene in scenes:
                start_idx = int(scene.start_time * sr)
                end_idx = int(scene.end_time * sr)
                energy = 0.0
                if start_idx < len(y):
                    segment = y[start_idx:min(end_idx, len(y))]
                    if len(segment) > 0:
                        energy = float(np.mean(librosa.feature.rms(y=segment)))
                updated_scenes.append(replace(scene, audio_energy=energy))
        except Exception as e:
            print(f"Audio analysis failed: {e}")
            return scenes
        return updated_scenes

    def detect_hooks_and_peaks(self, scenes: List[Scene]) -> List[Scene]:
        """Identify scenes that can serve as hooks or emotional peaks."""
        from dataclasses import replace
        if not scenes: return scenes

        # 1. Identify peaks
        cloned_scenes = []
        for scene in scenes:
            combined_intensity = scene.movement_score * 0.5 + scene.audio_energy * 50.0
            if combined_intensity > 5.0: # Arbitrary threshold
                scene = replace(scene, is_peak=True)
            cloned_scenes.append(scene)

        # 2. Identify best hook
        sorted_by_intensity = sorted(cloned_scenes, key=lambda x: x.movement_score * 0.5 + x.audio_energy * 50.0, reverse=True)
        if sorted_by_intensity:
            best_hook = sorted_by_intensity[0]
            # Replace the hook scene in the cloned list
            final_scenes = []
            for s in cloned_scenes:
                if s == best_hook:
                    final_scenes.append(replace(s, is_hook=True))
                else:
                    final_scenes.append(s)
            return final_scenes

        return cloned_scenes

    def generate_quality_scores(self, scenes: List[Scene], silences: List[Dict[str, float]]) -> List[Scene]:
        """Generate quality scores for each scene based on movement, audio, and presence of silence."""
        from dataclasses import replace
        scored_scenes = []
        for scene in scenes:
            # Base score from movement and audio
            score = min(scene.movement_score * 2.0 + scene.audio_energy * 100.0, 10.0)

            # Bonus for hooks and peaks
            if scene.is_hook: score += 2.0
            if scene.is_peak: score += 1.0

            # Penalize for overlapping with silence
            silence_penalty = 0
            for silence in silences:
                silence_start = silence['start']
                silence_end = silence.get('end', scene.end_time)

                overlap_start = max(scene.start_time, silence_start)
                overlap_end = min(scene.end_time, silence_end)

                if overlap_start < overlap_end:
                    overlap_duration = overlap_end - overlap_start
                    scene_duration = scene.end_time - scene.start_time
                    if scene_duration > 0:
                        silence_penalty += (overlap_duration / scene_duration) * 5.0

            final_score = max(0.0, score - silence_penalty)
            scored_scenes.append(replace(scene, score=final_score))

        return sorted(scored_scenes, key=lambda x: x.score, reverse=True)
