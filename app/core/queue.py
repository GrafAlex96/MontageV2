from redis import Redis
from rq import Queue
from app.core.config import settings

redis_conn = Redis.from_url(settings.REDIS_URL)
video_queue = Queue('video_processing', connection=redis_conn)

from rq import Retry

def enqueue_job(job_id: int):
    # This will be called by the bot handler
    from app.workers.video_worker import process_job_task
    video_queue.enqueue(process_job_task, job_id, job_id=str(job_id), retry=Retry(max=3))
