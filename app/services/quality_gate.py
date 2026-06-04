from typing import List, Dict, Any
from app.services.analysis import Scene

class QualityGate:
    def calculate_scores(self, timeline: List[Dict]) -> Dict[str, float]:
        """Calculate Engagement, Retention, and Visual Quality scores (0-100)."""
        if not timeline:
            return {"engagement": 0, "retention": 0, "visual_quality": 0}

        scenes = [item['scene'] for item in timeline]

        # Engagement: Based on average scene score and presence of hook
        avg_score = sum(s.score for s in scenes) / len(scenes)
        has_hook = any(s.is_hook for s in scenes)
        engagement = min(avg_score * 8.0 + (20 if has_hook else 0), 100.0)

        # Retention: Based on pacing (scene duration variety) and movement
        avg_duration = sum(s.end_time - s.start_time for s in scenes) / len(scenes)
        retention = min(100.0, 70.0 + (10 if avg_duration < 3.0 else 0))

        # Visual Quality: Based on movement score
        avg_movement = sum(s.movement_score for s in scenes) / len(scenes)
        visual_quality = min(avg_movement * 10.0 + 50.0, 100.0)

        return {
            "engagement": engagement,
            "retention": retention,
            "visual_quality": visual_quality
        }

    def is_production_ready(self, scores: Dict[str, float]) -> bool:
        """Single criteria for quality readiness."""
        return all(score >= 75 for score in scores.values())
