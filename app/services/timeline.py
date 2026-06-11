import logging
from typing import List, Dict
from dataclasses import dataclass
from app.services.analysis import Scene, VideoAnalyzer

logger = logging.getLogger(__name__)
from app.services.editor import Editor

@dataclass
class VideoClip:
    path: str
    scenes: List[Scene]

class TimelineManager:
    def __init__(self, target_duration: int, editing_rules: Dict = None, attempt: int = 0):
        self.target_duration = target_duration
        self.editing_rules = editing_rules or {}
        self.attempt = attempt

    def build_combined_timeline_from_items(self, candidate_items: List[Dict], clip_beats: Dict[str, List[float]] = None, mode: str = "VISUAL") -> List[Dict]:
        """
        Pure functional timeline construction. Strictly chooses between MUSIC or VISUAL mode.
        """
        from dataclasses import replace

        selected_timeline = []
        cumulative_cursor = 0.0

        min_dur = self.editing_rules.get('cut_rules', {}).get('min_duration', 1.0)
        max_dur = self.editing_rules.get('cut_rules', {}).get('max_duration', 5.0)

        # MUSIC MODE: uses the first clip with high-confidence beats as anchor
        global_beats = []
        if mode == "MUSIC" and clip_beats:
            for path, beats in clip_beats.items():
                if beats:
                    global_beats = beats
                    break

        for item in candidate_items:
            scene = item['scene']

            # 1. Clamp scene duration to rules
            original_duration = scene.end_time - scene.start_time
            duration = min(max(original_duration, min_dur), max_dur)

            # Update duration by creating a new scene object (immutable pattern)
            scene = replace(scene, end_time=scene.start_time + duration)

            # 2. Global-anchored beat-sync
            if global_beats:
                scene = self._sync_scene_to_beats(scene, global_beats, cumulative_cursor)
                duration = scene.end_time - scene.start_time

            # 3. Add to timeline if within total target
            if cumulative_cursor + duration <= self.target_duration:
                scene = replace(scene, timeline_offset=cumulative_cursor)
                selected_timeline.append({'path': item['path'], 'scene': scene})
                cumulative_cursor += duration
            elif cumulative_cursor < self.target_duration:
                # Final filling segment
                remaining = self.target_duration - cumulative_cursor
                if remaining > 0.3:
                    scene = replace(scene, end_time=scene.start_time + remaining, timeline_offset=cumulative_cursor)
                    selected_timeline.append({'path': item['path'], 'scene': scene})
                    cumulative_cursor += remaining

            if cumulative_cursor >= self.target_duration:
                break

        self._validate_timeline(selected_timeline)
        return selected_timeline

    def _validate_timeline(self, timeline: List[Dict]):
        """Ensure no overlaps or gaps in the final timeline."""
        if not timeline: return

        expected_cursor = 0.0
        for item in timeline:
            scene = item['scene']
            if abs(scene.timeline_offset - expected_cursor) > 0.01:
                logger.error(f"Timeline Drift Detected: {scene.timeline_offset} vs {expected_cursor}")
            expected_cursor += (scene.end_time - scene.start_time)

    def _sync_scene_to_beats(self, scene: Scene, beats: List[float], current_timeline_time: float) -> Scene:
        """Adjust a single scene's duration to align its end with a beat with strict limits."""
        from dataclasses import replace
        duration = scene.end_time - scene.start_time

        # Find beats strictly after the start of this scene
        beats_after_start = [b for b in beats if b > scene.start_time]
        if not beats_after_start:
            return scene

        # Pick the beat that minimizes deviation from original duration
        closest_beat = min(beats_after_start, key=lambda b: abs((b - scene.start_time) - duration))

        # Strict adjustment limit: max 0.5s deviation for rhythmic integrity
        if abs((closest_beat - scene.start_time) - duration) < 0.5:
            # Use replace for frozen dataclass
            return replace(scene, end_time=closest_beat)

        return scene

    def _sync_to_beats(self, timeline: List[Dict], beats: List[float]) -> List[Dict]:
        """Adjust clip durations to align with beats."""
        from dataclasses import replace
        current_time = 0.0
        synced_timeline = []

        for item in timeline:
            scene = item['scene']
            duration = scene.end_time - scene.start_time

            # Find the closest beat after current_time + duration
            target_time = current_time + duration
            beats_after = [b for b in beats if b >= target_time]
            closest_beat = min(beats_after, default=target_time)

            # If the beat is close enough, adjust duration
            if abs(closest_beat - target_time) < 1.0:
                new_scene = replace(scene, end_time=scene.start_time + (closest_beat - current_time))
                current_time = closest_beat
                synced_timeline.append({'path': item['path'], 'scene': new_scene})
            else:
                current_time += duration
                synced_timeline.append(item)

        return synced_timeline

    def build_fallback_timeline(self, video_paths: List[str]) -> List[Dict]:
        """
        SAFE-MODE FALLBACK: Creates a simple timeline by taking chunks from available videos
        without heavy analysis. Ensures the pipeline ALWAYS produces a video.
        """
        if not video_paths:
            logger.error("Fallback timeline failed: No video paths provided.")
            return []

        logger.warning(f"BUILDING FALLBACK TIMELINE for {len(video_paths)} videos")

        selected_timeline = []
        cumulative_cursor = 0.0

        # Filter out missing files
        valid_paths = [p for p in video_paths if os.path.exists(p)]
        if not valid_paths:
            logger.error("Fallback timeline failed: No valid video files found on disk.")
            return []

        # Calculate how much time to take from each video
        per_video_duration = self.target_duration / len(valid_paths)

        # Minimum segment duration to avoid flicker
        per_video_duration = max(per_video_duration, 2.0)

        for path in valid_paths:
            if cumulative_cursor >= self.target_duration:
                break

            remaining = self.target_duration - cumulative_cursor
            chunk_dur = min(per_video_duration, remaining)

            if chunk_dur < 0.1: break

            # Robust Scene creation:
            # We use a 1.0s start offset to bypass potential black frames/headers
            # and a fixed duration. FFmpeg/MoviePy will handle if the clip is shorter
            # by either erroring (which we catch) or just stopping.
            scene = Scene(
                start_time=0.0,
                end_time=chunk_dur,
                score=1.0,
                timeline_offset=cumulative_cursor
            )

            selected_timeline.append({'path': path, 'scene': scene})
            cumulative_cursor += chunk_dur

        return selected_timeline
