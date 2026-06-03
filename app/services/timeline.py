from typing import List, Dict
from dataclasses import dataclass
from app.services.analysis import Scene, VideoAnalyzer
from app.services.editor import Editor

@dataclass
class VideoClip:
    path: str
    scenes: List[Scene]

class TimelineManager:
    def __init__(self, target_duration: int):
        self.target_duration = target_duration

    def build_combined_timeline(self, clips: List[VideoClip], beats: List[float] = None) -> List[Dict]:
        """
        Combine scenes from multiple clips and select the best ones for the timeline.
        Returns a list of dicts with path and scene info.
        """
        all_scenes_with_source = []
        for clip in clips:
            for scene in clip.scenes:
                all_scenes_with_source.append({
                    'path': clip.path,
                    'scene': scene
                })

        # Sort all scenes by score
        all_scenes_with_source.sort(key=lambda x: x['scene'].score, reverse=True)

        selected_timeline = []
        current_total_duration = 0.0

        for item in all_scenes_with_source:
            scene = item['scene']
            duration = scene.end_time - scene.start_time

            if current_total_duration + duration <= self.target_duration:
                selected_timeline.append(item)
                current_total_duration += duration
            elif current_total_duration < self.target_duration:
                remaining = self.target_duration - current_total_duration
                if remaining > 1.0:
                    scene.end_time = scene.start_time + remaining
                    selected_timeline.append(item)
                    current_total_duration += remaining

            if current_total_duration >= self.target_duration:
                break

        # In multi-video mode, find the absolute best hook across all videos
        # and ensure it's at the absolute beginning.
        if not selected_timeline: return []

        # Sort all selected by score to find the best hook
        best_hook_item = max(selected_timeline, key=lambda x: x['scene'].score)

        others = [item for item in selected_timeline if item != best_hook_item]
        # Sort others chronologically within their respective videos
        others.sort(key=lambda x: (x['path'], x['scene'].start_time))

        final_selected = [best_hook_item] + others

        # Beat-sync if beats are available
        if beats:
            final_selected = self._sync_to_beats(final_selected, beats)

        return final_selected

    def _sync_to_beats(self, timeline: List[Dict], beats: List[float]) -> List[Dict]:
        """Adjust clip durations to align with beats."""
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
                scene.end_time = scene.start_time + (closest_beat - current_time)
                current_time = closest_beat
            else:
                current_time += duration

            synced_timeline.append(item)

        return synced_timeline
