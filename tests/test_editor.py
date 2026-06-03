import pytest
from app.services.analysis import Scene
from app.services.editor import Editor

def test_segment_selection():
    scenes = [
        Scene(start_time=0.0, end_time=10.0, score=8.0),
        Scene(start_time=10.0, end_time=20.0, score=5.0),
        Scene(start_time=20.0, end_time=30.0, score=9.0),
        Scene(start_time=30.0, end_time=40.0, score=2.0),
    ]

    editor = Editor(target_duration=15)
    selected = editor.select_best_segments(scenes)

    # Best is 20-30 (score 9), it becomes the hook.
    # Hook (20-30) is 10s. Remaining 5s.
    # Next best is 0-10 (score 8), will be trimmed to 5s.

    total_duration = sum(s.end_time - s.start_time for s in selected)
    assert total_duration == 15.0
    assert len(selected) == 2
    # Hook should be first in social media style
    assert selected[0].start_time == 20.0
    assert selected[1].start_time == 0.0
