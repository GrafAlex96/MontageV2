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
        Implements a deterministic retry strategy ladder with immutable Scene objects.
        """
        import copy
        from dataclasses import replace

        selected_timeline = []

        # Rule enforcement: Cut duration
        min_dur = self.editing_rules.get('cut_rules', {}).get('min_duration', 1.0)
        max_dur = self.editing_rules.get('cut_rules', {}).get('max_duration', 5.0)

        # --- RETRY STRATEGY LADDER ---
        # Note: Scene is now frozen, so we create clones with replaced values
        processed_candidates = []
        for i in candidate_items:
            scene = i['scene']
            if self.attempt == 1 and scene.is_hook:
                scene = replace(scene, score=scene.score * 1.5)
            elif self.attempt == 2 and scene.is_peak:
                scene = replace(scene, score=scene.score * 1.5)
            processed_candidates.append({'path': i['path'], 'scene': scene})

        if self.attempt in [1, 2]:
            processed_candidates.sort(key=lambda x: x['scene'].score, reverse=True)

        if self.attempt == 3: # Shorten cuts (-20%)
            min_dur *= 0.8
            max_dur *= 0.8

        elif self.attempt == 4: # Re-order by motion intensity
            processed_candidates.sort(key=lambda x: x['scene'].movement_score, reverse=True)

        elif self.attempt >= 5: # Fallback: disable beat sync
            clip_beats = None

        # Re-ensure hook is first after any re-sorting
        hooks = [i for i in processed_candidates if i['scene'].is_hook]
        non_hooks = [i for i in processed_candidates if not i['scene'].is_hook]
        if hooks:
            processed_candidates = [hooks[0]] + [h for h in hooks[1:]] + non_hooks

        # Global timeline cursor to prevent gaps or overlaps
        cumulative_cursor = 0.0

        for item in processed_candidates:
            scene = item['scene']

            # 1. Clamp scene duration to rules
            original_duration = scene.end_time - scene.start_time
            duration = min(max(original_duration, min_dur), max_dur)

            # Update duration by creating a new scene object (immutable pattern)
            scene = replace(scene, end_time=scene.start_time + duration)

            # 2. Individual beat-sync for this clip
            if clip_beats and item['path'] in clip_beats:
                beats = clip_beats[item['path']]
                if beats:
                    scene = self._sync_scene_to_beats(scene, beats, cumulative_cursor)
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
        duration = scene.end_time - scene.start_time

        # Find beats strictly after the start of this scene
        beats_after_start = [b for b in beats if b > scene.start_time]
        if not beats_after_start:
            return scene

        # Pick the beat that minimizes deviation from original duration
        closest_beat = min(beats_after_start, key=lambda b: abs((b - scene.start_time) - duration))

        # Strict adjustment limit: max 0.5s deviation for rhythmic integrity
        if abs((closest_beat - scene.start_time) - duration) < 0.5:
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
