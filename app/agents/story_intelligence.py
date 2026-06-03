from typing import List, Dict, Any
from app.services.analysis import Scene
import logging

logger = logging.getLogger(__name__)

class StoryIntelligence:
    def analyze_content(self, scenes: List[Scene]) -> Dict[str, Any]:
        """
        Extract a minimal and strictly structured semantic understanding of the video.
        """
        if not scenes:
            return {
                "story_type": "entertainment",
                "key_message": "No scenes detected",
                "key_scenes": [],
                "emotional_arc": []
            }

        # Simplified story type detection
        avg_movement = sum(s.movement_score for s in scenes) / len(scenes)
        if avg_movement < 1.0:
            story_type = "informational"
        elif avg_movement > 5.0:
            story_type = "transformation"
        else:
            story_type = "entertainment"

        # Extract exactly 3-7 key scenes based on score
        sorted_scenes = sorted(scenes, key=lambda x: x.score, reverse=True)
        key_scenes = sorted_scenes[:min(7, max(3, len(scenes)))]

        return {
            "story_type": story_type,
            "key_message": f"Visual {story_type} narrative",
            "key_scenes": key_scenes,
            "emotional_arc": [round(s.score, 2) for s in scenes]
        }
