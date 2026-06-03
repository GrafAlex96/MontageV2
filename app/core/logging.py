import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(trace_id)s'
    )
    handler.setFormatter(formatter)

    file_handler = logging.FileHandler("app.json.log")
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
