import logging
import os
import shutil
from sqlalchemy import select, update
from app.db.session import get_db
from app.db.models import Job, JobStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

def recover_interrupted_jobs():
    """Identify and fail jobs that were interrupted by a system shutdown."""
    logger.info("🔄 Running job recovery...")

    with get_db() as session:
        # Find jobs that are in intermediate states
        interrupted_states = [
            JobStatus.ANALYZING,
            JobStatus.PROCESSING,
            JobStatus.RENDERING,
            JobStatus.POST_PROCESSING
        ]

        stmt = select(Job).where(Job.status.in_(interrupted_states))
        jobs = session.execute(stmt).scalars().all()

        for job in jobs:
            logger.warning(f"Failing interrupted job {job.id} (Status: {job.status})")
            session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(status=JobStatus.FAILED, error_message="Interrupted by system shutdown/restart")
            )

        session.commit()

    logger.info(f"Recovered {len(jobs)} jobs.")

def cleanup_stale_artifacts():
    """Clean up temp storage files that aren't referenced by active jobs."""
    logger.info("🧹 Cleaning up stale artifacts...")
    if not os.path.exists(settings.TEMP_STORAGE_PATH):
        return

    # Simple strategy: clean everything in temp_storage if it's older than 1 day
    # Or just wipe it on startup if we've already failed all interrupted jobs
    import time
    now = time.time()

    for filename in os.listdir(settings.TEMP_STORAGE_PATH):
        file_path = os.path.join(settings.TEMP_STORAGE_PATH, filename)
        if os.path.isfile(file_path):
            # If older than 2 hours, delete it
            if now - os.path.getmtime(file_path) > 7200:
                try:
                    os.remove(file_path)
                    logger.debug(f"Deleted stale file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    recover_interrupted_jobs()
    cleanup_stale_artifacts()
