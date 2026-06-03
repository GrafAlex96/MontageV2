from typing import List
from app.services.analysis import Scene

class Editor:
    def __init__(self, target_duration: int):
        self.target_duration = target_duration

    def select_best_segments(self, scenes: List[Scene]) -> List[Scene]:
        """Select the best segments and structure them as Setup -> Hook -> Development -> Peak -> Ending."""
        if not scenes: return []

        hooks = [s for s in scenes if s.is_hook]
        peaks = [s for s in scenes if s.is_peak and not s.is_hook]
        others = [s for s in scenes if not s.is_hook and not s.is_peak]

        # Sort by score
        hooks.sort(key=lambda x: x.score, reverse=True)
        peaks.sort(key=lambda x: x.score, reverse=True)
        others.sort(key=lambda x: x.score, reverse=True)

        selected_hook = hooks[0] if hooks else (peaks[0] if peaks else others[0])

        # Plan the structure
        # Target duration breakdown (rough):
        # Hook: 15%
        # Setup: 15%
        # Development: 40%
        # Peak: 20%
        # Ending: 10%

        structure = []
        current_duration = 0.0

        # 1. Hook (Must be strong, will be moved to front later)
        structure.append(selected_hook)
        current_duration += (selected_hook.end_time - selected_hook.start_time)

        # 2. Fill the rest with best remaining scenes
        remaining_scenes = [s for s in scenes if s != selected_hook]
        remaining_scenes.sort(key=lambda x: x.score, reverse=True)

        for scene in remaining_scenes:
            if current_duration >= self.target_duration:
                break

            duration = scene.end_time - scene.start_time
            if current_duration + duration <= self.target_duration:
                structure.append(scene)
                current_duration += duration
            else:
                remaining = self.target_duration - current_duration
                if remaining > 1.0:
                    import copy
                    scene_copy = copy.copy(scene)
                    scene_copy.end_time = scene_copy.start_time + remaining
                    structure.append(scene_copy)
                    current_duration += remaining

        # 3. Order the structure: Setup -> Hook -> Development -> Peak -> Ending
        # For simplicity in this logic, we'll ensure Hook is at the start as per social media rules.
        # But we also want narrative flow.
        # Let's find the most "ending-like" (usually late in video) and "setup-like" (early).

        hook = selected_hook
        others = [s for s in structure if s != hook]
        others.sort(key=lambda x: x.start_time) # Chronological for narrative

        # Hook first, then the rest
        final_selected = [hook] + others
        return final_selected
