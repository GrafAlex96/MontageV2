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
        """
        # 1. Collect all scenes
        all_items = []
        for clip in clips:
            for scene in clip.scenes:
                all_items.append({'path': clip.path, 'scene': scene})

        # 2. Extract semantic data (using first clip as anchor)
        story_data = self.story_intel.analyze_content(clips[0].scenes if clips else [])

        # 3. Get Director suggestions
        suggestions = self.director.suggest_strategy(story_data)

        # 4. Master Editor resolves all and decides the final order/hook
        final_decision = self.master_editor.decide_final_strategy(
            story_data, suggestions, all_items
        )

        # 5. Lock technical rules from presets
        editing_rules = self.presets.get_rules(final_decision["final_preset"])

        return {
            "strategy": final_decision,
            "rules": editing_rules,
            "story_type": story_data["story_type"]
        }
