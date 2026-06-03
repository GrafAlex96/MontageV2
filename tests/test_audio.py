import pytest
import os
import subprocess
from app.services.audio import AudioService

def test_audio_normalization():
    service = AudioService()
    input_video = "sample_video.mp4"
    output_video = "normalized_video.mp4"

    if os.path.exists(output_video):
        os.remove(output_video)

    service.normalize_audio(input_video, output_video)

    assert os.path.exists(output_video)
    assert os.path.getsize(output_video) > 0

    if os.path.exists(output_video):
        os.remove(output_video)

def test_audio_clarity():
    service = AudioService()
    input_video = "sample_video.mp4"
    output_video = "clarity_video.mp4"

    if os.path.exists(output_video):
        os.remove(output_video)

    service.improve_clarity(input_video, output_video)

    assert os.path.exists(output_video)

    if os.path.exists(output_video):
        os.remove(output_video)
