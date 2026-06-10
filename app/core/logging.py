import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    # Strict JSON format as requested in Directive v1.0
    formatter = jsonlogger.JsonFormatter(
        '{"trace_id": "%(trace_id)s", "stage": "%(stage)s", "timestamp": "%(asctime)s", "status": "%(status)s", "details": %(details)s, "duration_ms": %(duration_ms)s, "error": "%(error)s"}'
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
