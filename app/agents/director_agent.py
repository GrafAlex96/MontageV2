from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DirectorAgent:
    def suggest_strategy(self, story_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide non-final suggestions for editing style and strategy.
        """
        story_type = story_data.get("story_type", "entertainment")

        preset = "reels_standard"
        if story_type == "transformation":
            preset = "viral_hype"
        elif story_type == "informational":
            preset = "talking_head"

        hook_strategy = "visual"
        if preset == "viral_hype":
            hook_strategy = "curiosity_gap"

        return {
            "suggested_preset": preset,
            "suggested_pacing": "fast" if preset == "viral_hype" else "medium",
            "suggested_hook_strategy": hook_strategy
        }
