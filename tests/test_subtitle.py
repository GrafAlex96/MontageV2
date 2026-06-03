import pytest
from unittest.mock import MagicMock, patch
from app.services.subtitle import SubtitleService

def test_format_timestamp():
    service = SubtitleService()
    assert service._format_timestamp(61.5) == "00:01:01,500"
    assert service._format_timestamp(3661.005) == "01:01:01,005"

@patch('whisper.load_model')
def test_transcribe(mock_load_model):
    mock_model = MagicMock()
    mock_load_model.return_value = mock_model
    mock_model.transcribe.return_value = {
        'segments': [
            {
                'words': [
                    {'word': 'Hello', 'start': 0.0, 'end': 0.5, 'probability': 0.9},
                    {'word': 'world', 'start': 0.5, 'end': 1.0, 'probability': 0.9}
                ]
            }
        ]
    }

    # We need to mock os.path.exists too
    with patch('os.path.exists', return_value=True):
        service = SubtitleService()
        segments = service.transcribe("dummy.mp4")

        assert len(segments) == 1
        assert "Hello" in segments[0]['word']
        assert "world" in segments[0]['word']
