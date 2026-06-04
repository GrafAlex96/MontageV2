from typing import List, Dict, Any
import logging
from app.services.analysis import Scene
from app.agents.story_intelligence import StoryIntelligence
from app.agents.director_agent import DirectorAgent
from app.agents.master_editor import MasterEditor
from app.agents.editing_presets import EditingPresets

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """
    Single source of truth for all editing decisions.
    Controls scene selection, timeline structure, and style application.
    """
    def __init__(self):
        self.story_intel = StoryIntelligence()
        self.director = DirectorAgent()
        self.master_editor = MasterEditor()
        self.presets = EditingPresets()

    def create_master_plan(self, clips: List[Any], target_duration: int) -> Dict[str, Any]:
        """
        Consolidate all suggestions into ONE final master plan.
        Single authority for all pipeline decisions.
        """
        # 1. Collect all scenes
        all_items = []
        for clip in clips:
            for scene in clip.scenes:
                all_items.append({'path': clip.path, 'scene': scene})

        # 2. Extract semantic data (Helper call)
        story_data = self.story_intel.analyze_content(clips[0].scenes if clips else [])

        # 3. Get Director suggestions (Helper call)
        suggestions = self.director.suggest_strategy(story_data)

        # 4. Final Decision Authority (Master Editor as tool)
        # Here we enforce deterministic rules directly in orchestrator if needed
        final_decision = self.master_editor.decide_final_strategy(
            story_data, suggestions, all_items
        )

        # 5. Apply style rules from Presets
        editing_rules = self.presets.get_rules(final_decision["final_preset"])

        # 6. Global Decision: Decide if we use MUSIC or VISUAL mode for beat-sync
        # Music mode only if high confidence and suitable story type
        beat_sync_mode = "VISUAL"
        if final_decision["final_preset"] in ["viral_hype", "storytelling"]:
             beat_sync_mode = "MUSIC"

        return {
            "strategy": final_decision,
            "rules": editing_rules,
            "story_type": story_data["story_type"],
            "beat_sync_mode": beat_sync_mode
        }
