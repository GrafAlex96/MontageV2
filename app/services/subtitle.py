import whisper
import os
import logging
from typing import List, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

class SubtitleService:
    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = whisper.load_model(self.model_name)
        return self._model

    def unload_model(self):
        """Free up memory by unloading the model."""
        import gc
        import torch
        if self._model:
             logger.info("Hard Unloading Whisper Model...")
             # Explicitly delete all references to Whisper internals
             del self._model
             self._model = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Aggressive deep cleanup
        try:
            # Force cleanup of all generations multiple times
            for _ in range(3):
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except:
            pass

        logger.info("Whisper model unloaded and memory reclaimed.")

    def transcribe(self, video_path: str) -> List[Dict]:
        """Transcribe video and return short word-level segments (viral style)."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        result = self.model.transcribe(video_path, verbose=False, word_timestamps=True)

        segments = []
        # Social media style: 2-5 words per line (semantic chunks)
        temp_words = []
        for segment in result.get('segments', []):
            for word in segment.get('words', []):
                temp_words.append(word)
                # Group into chunks of 3 words for better readability
                if len(temp_words) >= 3 or word['word'].endswith(('.', '!', '?')):
                    segments.append({
                        'word': " ".join([w['word'].strip() for w in temp_words]),
                        'start': temp_words[0]['start'],
                        'end': temp_words[-1]['end'],
                        'probability': sum([w['probability'] for w in temp_words]) / len(temp_words)
                    })
                    temp_words = []

        # Flush remaining
        if temp_words:
            segments.append({
                'word': " ".join([w['word'].strip() for w in temp_words]),
                'start': temp_words[0]['start'],
                'end': temp_words[-1]['end'],
                'probability': sum([w['probability'] for w in temp_words]) / len(temp_words)
            })
        return segments

    def generate_srt(self, word_segments: List[Dict]) -> str:
        """Convert word segments to SRT format (simple version)."""
        srt_content = ""
        for i, segment in enumerate(word_segments):
            start = self._format_timestamp(segment['start'])
            end = self._format_timestamp(segment['end'])
            srt_content += f"{i+1}\n{start} --> {end}\n{segment['word'].strip()}\n\n"
        return srt_content

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
