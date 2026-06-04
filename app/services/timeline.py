from typing import List, Dict
from dataclasses import dataclass
from app.services.analysis import Scene, VideoAnalyzer
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

    def build_combined_timeline_from_items(self, candidate_items: List[Dict], clip_beats: Dict[str, List[float]] = None) -> List[Dict]:
        """
        Build the final timeline using candidates selected by Master Editor.
        Implements a deterministic retry strategy ladder.
        """
        import copy
        selected_timeline = []
        current_total_duration = 0.0

        # Rule enforcement: Cut duration
        min_dur = self.editing_rules.get('cut_rules', {}).get('min_duration', 1.0)
        max_dur = self.editing_rules.get('cut_rules', {}).get('max_duration', 5.0)

        # --- RETRY STRATEGY LADDER ---
        processed_candidates = [copy.deepcopy(i) for i in candidate_items]

        if self.attempt == 1: # Boost hook weight
            for i in processed_candidates:
                if i['scene'].is_hook: i['scene'].score *= 1.5
            processed_candidates.sort(key=lambda x: x['scene'].score, reverse=True)

        elif self.attempt == 2: # Boost peak weight
            for i in processed_candidates:
                if i['scene'].is_peak: i['scene'].score *= 1.5
            processed_candidates.sort(key=lambda x: x['scene'].score, reverse=True)

        elif self.attempt == 3: # Shorten cuts (-20%)
            min_dur *= 0.8
            max_dur *= 0.8

        elif self.attempt == 4: # Re-order by motion intensity
            processed_candidates.sort(key=lambda x: x['scene'].movement_score, reverse=True)

        elif self.attempt >= 5: # Fallback: disable beat sync (handled via clip_beats = None)
            clip_beats = None

        # Re-ensure hook is first after any re-sorting
        hooks = [i for i in processed_candidates if i['scene'].is_hook]
        non_hooks = [i for i in processed_candidates if not i['scene'].is_hook]
        if hooks:
            processed_candidates = [hooks[0]] + [h for h in hooks[1:]] + non_hooks

        # Global timeline cursor to prevent gaps or overlaps
        cumulative_cursor = 0.0

        for item in processed_candidates:
            item_copy = {
                'path': item['path'],
                'scene': copy.deepcopy(item['scene']) # Deep copy to be safe
            }
            scene = item_copy['scene']

            # 1. Clamp scene duration to rules
            original_duration = scene.end_time - scene.start_time
            duration = min(max(original_duration, min_dur), max_dur)
            scene.end_time = scene.start_time + duration

            # 2. Individual beat-sync for this clip
            if clip_beats and item['path'] in clip_beats:
                beats = clip_beats[item['path']]
                if beats:
                    scene = self._sync_scene_to_beats(scene, beats, cumulative_cursor)
                    duration = scene.end_time - scene.start_time

            # 3. Add to timeline if within total target
            if cumulative_cursor + duration <= self.target_duration:
                scene.timeline_offset = cumulative_cursor
                selected_timeline.append(item_copy)
                cumulative_cursor += duration
            elif cumulative_cursor < self.target_duration:
                # Final filling segment
                remaining = self.target_duration - cumulative_cursor
                if remaining > 0.3: # Minimum useful short segment
                    scene.end_time = scene.start_time + remaining
                    scene.timeline_offset = cumulative_cursor
                    selected_timeline.append(item_copy)
                    cumulative_cursor += remaining

            if current_total_duration >= self.target_duration:
                break

        return selected_timeline

    def _sync_scene_to_beats(self, scene: Scene, beats: List[float], current_timeline_time: float) -> Scene:
        """Adjust a single scene's duration to align its end with a beat."""
        duration = scene.end_time - scene.start_time
        target_absolute_time = current_timeline_time + duration

        # This is tricky because we don't have the global timeline beats,
        # only local clip beats. We want the CLIP'S relative beat.
        # local_end_time = scene.end_time
        closest_beat = min([b for b in beats if b >= scene.start_time], default=scene.end_time)

        # If there's a beat within a reasonable distance of the original end, snap to it
        beats_after_start = [b for b in beats if b > scene.start_time]
        if beats_after_start:
            # Pick a beat that makes the duration close to original
            closest_beat = min(beats_after_start, key=lambda b: abs((b - scene.start_time) - duration))
            if abs((closest_beat - scene.start_time) - duration) < 1.0:
                scene.end_time = closest_beat

        return scene

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
