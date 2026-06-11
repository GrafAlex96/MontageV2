import logging
import sys
from pythonjsonlogger import jsonlogger

class SafeJsonFormatter(jsonlogger.JsonFormatter):
    """Prevents KeyError when log records are missing custom fields."""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        defaults = {
            'trace_id': 'SYSTEM',
            'stage': 'general',
            'status': 'info',
            'details': {},
            'duration_ms': 0,
            'error': ''
        }
        for key, val in defaults.items():
            if key not in log_record:
                log_record[key] = val

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    # Flexible JSON format to handle both system and custom logs
    formatter = SafeJsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)

    file_handler = logging.FileHandler("logs/app.json.log")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)

    # Set levels for noisy libraries
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("moviepy").setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger("video_editor")
