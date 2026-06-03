import pytest
from app.services.analysis import Scene
from app.services.timeline import TimelineManager, VideoClip

def test_combined_timeline():
    clip1 = VideoClip(path="video1.mp4", scenes=[
        Scene(start_time=0.0, end_time=10.0, score=5.0),
        Scene(start_time=10.0, end_time=20.0, score=9.0)
    ])
    clip2 = VideoClip(path="video2.mp4", scenes=[
        Scene(start_time=0.0, end_time=10.0, score=8.0),
        Scene(start_time=10.0, end_time=20.0, score=2.0)
    ])

    manager = TimelineManager(target_duration=15)
    timeline = manager.build_combined_timeline([clip1, clip2])

    # Due to default min/max duration rules in Director system:
    # min_dur = 1.0, max_dur = 5.0
    # Best (9.0) was 10s, now capped at 5s.
    # Next (8.0) was 10s, now capped at 5s.
    # Next (5.0) was 10s, now capped at 5s.
    # Total = 5+5+5 = 15s.

    assert len(timeline) == 3
    assert timeline[0]['path'] == "video1.mp4"
    # Both paths could be here since multiple clips are merged
    paths = [item['path'] for item in timeline]
    assert "video1.mp4" in paths
    assert "video2.mp4" in paths
