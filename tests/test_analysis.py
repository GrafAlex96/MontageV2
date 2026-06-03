import pytest
from app.services.analysis import VideoAnalyzer, Scene

def test_quality_scoring():
    # Mock data
    scenes = [
        Scene(start_time=0.0, end_time=5.0, movement_score=2.0, audio_energy=0.05, is_hook=True),
        Scene(start_time=5.0, end_time=10.0, movement_score=0.5, audio_energy=0.0, is_hook=False)
    ]
    silences = [
        {'start': 6.0, 'end': 9.0} # Silence in second scene
    ]

    analyzer = VideoAnalyzer("sample_video.mp4")
    scored_scenes = analyzer.generate_quality_scores(scenes, silences)

    # Scene 0: score = min(2.0*2.0 + 0.05*100, 10.0) + 2.0 (hook bonus) = 9.0 + 2.0 = 11.0
    # Scene 1: score = min(0.5*2.0 + 0, 10.0) - 3.0 (silence) = 1.0 - 3.0 = 0.0

    assert scored_scenes[0].score == 11.0
    assert scored_scenes[1].score == 0.0

def test_hook_detection():
    scenes = [
        Scene(start_time=0.0, end_time=5.0, movement_score=10.0, audio_energy=0.1),
        Scene(start_time=5.0, end_time=10.0, movement_score=1.0, audio_energy=0.0)
    ]
    analyzer = VideoAnalyzer("sample_video.mp4")
    hooked_scenes = analyzer.detect_hooks_and_peaks(scenes)
    assert hooked_scenes[0].is_hook == True
    assert hooked_scenes[0].is_peak == True

def test_scene_detection():
    # This requires an actual video file
    analyzer = VideoAnalyzer("sample_video.mp4")
    scenes = analyzer.detect_scenes()
    assert len(scenes) > 0
    assert scenes[0].start_time == 0.0
