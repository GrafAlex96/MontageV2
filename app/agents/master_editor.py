from typing import List, Dict, Any
from app.services.analysis import Scene
import logging

logger = logging.getLogger(__name__)

class MasterEditor:
    def _deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prevent random scene duplication across multiple videos."""
        seen = set()
        unique = []
        for item in items:
            s = item['scene']
            # Fingerprint: (path, start, end)
            fingerprint = (item['path'], round(s.start_time, 2), round(s.end_time, 2))
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique.append(item)
        return unique

    def decide_final_strategy(
        self,
        story_data: Dict[str, Any],
        director_suggestions: Dict[str, Any],
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        The ONLY authority that decides final editing strategy.
        Resolves conflicts and produces ONE unified plan.
        """
        # 0. Deduplicate
        unique_items = self._deduplicate_items(items)

        # 1. Resolve Preset
        final_preset = director_suggestions.get("suggested_preset", "reels_standard")

        # 2. Resolve Hook (Global strongest hook)
        all_potential_hooks = [i for i in unique_items if i['scene'].is_hook or i['scene'].is_peak]
        if not all_potential_hooks:
            all_potential_hooks = sorted(unique_items, key=lambda x: x['scene'].score, reverse=True)

        final_hook_item = all_potential_hooks[0] if all_potential_hooks else (unique_items[0] if unique_items else None)

        # 3. Resolve Scene Order (Chronological by source path then start_time, with Hook First)
        other_items = [i for i in unique_items if i != final_hook_item]
        # Sort by path to keep clips from same video together, then chronological
        other_items.sort(key=lambda x: (x['path'], x['scene'].start_time))

        final_timeline = [final_hook_item] + other_items if final_hook_item else other_items

        # 4. Final Pacing Rules
        pacing = director_suggestions.get("suggested_pacing", "medium")

        return {
            "final_preset": final_preset,
            "final_hook_strategy": director_suggestions.get("suggested_hook_strategy", "visual"),
            "final_timeline": final_timeline,
            "final_pacing_rules": {
                "pacing": pacing,
                "target_fps": 30
            },
            "confidence_score": 100 # Single user authority
        }
