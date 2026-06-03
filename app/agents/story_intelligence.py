from typing import List, Dict, Any
from app.services.analysis import Scene
import logging

logger = logging.getLogger(__name__)

class StoryIntelligence:
    def analyze_content(self, scenes: List[Scene]) -> Dict[str, Any]:
        """
        Analyze the semantic structure of the video based on scene metadata.
        Groups scenes into Setup -> Development -> Climax -> Resolution.
        """
        if not scenes:
            return {}

        total_scenes = len(scenes)

        # Simple heuristic-based semantic grouping for non-breaking extension
        # In a real scenario, this would use Vision LLMs or text analysis from transcription

        setup = scenes[:max(1, int(total_scenes * 0.2))]
        resolution = scenes[-max(1, int(total_scenes * 0.1)):] if total_scenes > 2 else []

        # Development and Climax are in the middle
        mid_start = len(setup)
        mid_end = len(scenes) - len(resolution)
        middle = scenes[mid_start:mid_end]

        # Climax is usually the peak energy moment in the middle/end
        climax = []
        development = []
        if middle:
            peak_scene = max(middle, key=lambda x: x.score)
            climax = [peak_scene]
            development = [s for s in middle if s != peak_scene]

        # Determine story type based on audio/visual cues
        avg_movement = sum(s.movement_score for s in scenes) / total_scenes
        story_type = "entertainment"
        if avg_movement < 1.0:
            story_type = "informational" # talking head?
        elif avg_movement > 5.0:
            story_type = "transformation" # high action/fast cuts

        return {
            "story_type": story_type,
            "key_message": "Automated story extraction based on visual energy",
            "emotional_arc": [s.score for s in scenes],
            "scene_groups": {
                "setup": setup,
                "development": development,
                "climax": climax,
                "resolution": resolution
            },
            "critical_scenes": [s for s in scenes if s.is_hook or s.is_peak]
        }
