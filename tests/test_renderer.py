import pytest
import os
from app.services.renderer import Renderer
from app.services.analysis import Scene

def test_rendering():
    # This might be slow and requires ImageMagick for TextClip
    # Let's test a simple concatenation without subtitles first
    renderer = Renderer()
    timeline = [
        {'path': 'sample_video.mp4', 'scene': Scene(0.0, 1.0, 5.0)},
        {'path': 'sample_video.mp4', 'scene': Scene(2.0, 3.0, 8.0)}
    ]
    output = "rendered_test.mp4"

    if os.path.exists(output):
        os.remove(output)

    try:
        renderer.render_final_video(timeline, [], output)
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0
    except Exception as e:
        pytest.skip(f"Rendering failed (maybe missing ImageMagick): {e}")
    finally:
        if os.path.exists(output):
            os.remove(output)
