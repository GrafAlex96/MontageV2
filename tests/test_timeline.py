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

    # Best is clip1 scene2 (9.0), then clip2 scene1 (8.0)
    # Clip1 Scene2: 10s. Remaining 5s.
    # Clip2 Scene1: 10s, will be trimmed to 5s.

    assert len(timeline) == 2
    assert timeline[0]['path'] == "video1.mp4"
    assert timeline[1]['path'] == "video2.mp4"
    assert timeline[1]['scene'].end_time - timeline[1]['scene'].start_time == 5.0
