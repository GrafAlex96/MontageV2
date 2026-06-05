import logging
from rq import Worker, Queue
from app.core.queue import redis_conn
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rq_worker")

def run_worker():
    """
    Standardized RQ Worker entrypoint.
    Listens to 'video_processing' queue.
    """
    try:
        # Check connection first
        redis_conn.ping()

        worker = Worker(['video_processing'], connection=redis_conn)
        logger.info("🚀 RQ Worker started. Listening for 'video_processing'...")
        worker.work(with_scheduler=True)
    except Exception as e:
        logger.error(f"❌ Worker failed to start: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_worker()
