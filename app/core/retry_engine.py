from typing import List, Dict, Any
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class RetryEngine:
    """
    Single authority for all retry decisions.
    Ensures deterministic variations and improvements.
    """
    def __init__(self):
        self.max_retries = settings.MAX_RETRIES

    def get_retry_strategy(self, attempt: int, base_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce a new strategy based on the retry ladder.
        """
        new_rules = base_rules.copy()

        if attempt == 1: # Level 1: Shorten clips (-10%)
            logger.info("Retry Level 1: Shortening clip durations by 10%")
            if 'cut_rules' in new_rules:
                new_rules['cut_rules']['max_duration'] *= 0.9

        elif attempt == 2: # Level 2: High-score prioritization
            logger.info("Retry Level 2: Prioritizing high-score scenes")
            # This logic is mostly handled in MasterEditor/TimelineManager
            new_rules['priority_mode'] = 'high_score'

        elif attempt >= 3: # Level 3: Fallback (Disable Sync)
            logger.info("Retry Level 3: Disabling beat-sync fallback")
            new_rules['disable_sync'] = True

        return new_rules

    def should_continue(self, attempt: int, current_score: float, previous_score: float) -> bool:
        """
        Stop retry loop if improvements are negligible (< 2%).
        """
        if attempt >= self.max_retries:
            return False

        if previous_score > 0 and (current_score - previous_score) / previous_score < 0.02:
            logger.info(f"Negligible improvement ({current_score} vs {previous_score}), stopping retries.")
            return False

        return True
