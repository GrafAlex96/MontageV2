from typing import List, Dict
from dataclasses import dataclass
from app.services.analysis import Scene, VideoAnalyzer
from app.services.editor import Editor

@dataclass
class VideoClip:
    path: str
    scenes: List[Scene]

class TimelineManager:
    def __init__(self, target_duration: int, editing_rules: Dict = None):
        self.target_duration = target_duration
        self.editing_rules = editing_rules or {}

    def build_combined_timeline_from_items(self, candidate_items: List[Dict], beats: List[float] = None) -> List[Dict]:
        """
        Build the final timeline using candidates selected by Master Editor.
        Candidate items are already ordered (Hook first).
        """
        selected_timeline = []
        current_total_duration = 0.0

        # Rule enforcement: Cut duration
        min_dur = self.editing_rules.get('cut_rules', {}).get('min_duration', 1.0)
        max_dur = self.editing_rules.get('cut_rules', {}).get('max_duration', 5.0)

        for item in candidate_items:
            scene = item['scene']

            duration = min(max(scene.end_time - scene.start_time, min_dur), max_dur)
            scene.end_time = scene.start_time + duration

            if current_total_duration + duration <= self.target_duration:
                selected_timeline.append(item)
                current_total_duration += duration
            elif current_total_duration < self.target_duration:
                remaining = self.target_duration - current_total_duration
                if remaining > 0.5: # Lowered threshold for single user quality
                    scene.end_time = scene.start_time + remaining
                    selected_timeline.append(item)
                    current_total_duration += remaining

            if current_total_duration >= self.target_duration:
                break

        if beats:
            selected_timeline = self._sync_to_beats(selected_timeline, beats)

        return selected_timeline

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
