from typing import Dict, Any

class EditingPresets:
    """
    Define deterministic technical constraints based on style.
    Presets MUST NOT influence story decisions.
    """
    PRESETS = {
        "viral_hype": {
            "cut_rules": {"min_duration": 0.3, "max_duration": 1.5}, # Slightly relaxed for quality
            "transition_rules": {"type": "zoom", "frequency": "high"},
            "subtitle_style": {"highlight": True, "pacing": "fast"},
            "pacing_rules": {"target_fps": 30, "pattern_interrupts": True}
        },
        "cinematic": {
            "cut_rules": {"min_duration": 3.0, "max_duration": 10.0},
            "transition_rules": {"type": "fade", "frequency": "low"},
            "subtitle_style": {"highlight": False, "pacing": "slow"},
            "pacing_rules": {"target_fps": 24, "pattern_interrupts": False}
        },
        "reels_standard": {
            "cut_rules": {"min_duration": 1.0, "max_duration": 3.0},
            "transition_rules": {"type": "cut", "frequency": "medium"},
            "subtitle_style": {"highlight": True, "pacing": "medium"},
            "pacing_rules": {"target_fps": 30, "pattern_interrupts": True}
        },
        "storytelling": {
            "cut_rules": {"min_duration": 2.0, "max_duration": 5.0},
            "transition_rules": {"type": "dissolve", "frequency": "medium"},
            "subtitle_style": {"highlight": True, "pacing": "medium"},
            "pacing_rules": {"target_fps": 30, "pattern_interrupts": True}
        },
        "talking_head": {
            "cut_rules": {"min_duration": 1.0, "max_duration": 5.0},
            "transition_rules": {"type": "cut", "frequency": "low"},
            "subtitle_style": {"highlight": True, "pacing": "sync_with_speech"},
            "pacing_rules": {"target_fps": 30, "pattern_interrupts": False}
        }
    }

    def get_rules(self, preset_name: str) -> Dict[str, Any]:
        return self.PRESETS.get(preset_name, self.PRESETS["reels_standard"])
