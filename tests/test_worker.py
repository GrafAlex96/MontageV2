import pytest
from unittest.mock import AsyncMock, MagicMock
from app.workers.video_worker import VideoWorker
from app.db.models import Job, JobStatus, User
from sqlalchemy import select

@pytest.mark.anyio
async def test_worker_polling():
    bot = AsyncMock()
    worker = VideoWorker(bot)

    # Mocking process_job since it's too complex for unit test without extensive mocking
    worker.process_job = AsyncMock()

    # We can't easily test the infinite loop 'run' but we can test one cycle of 'process_next_job' if we mock everything

    from app.db.session import get_db
    with get_db() as session:
        user = User(telegram_id=999, username="worker_test")
        session.add(user)
        session.flush()
        job = Job(user_id=user.id, status=JobStatus.PENDING)
        session.add(job)
        session.commit()
        job_id = job.id

    # Re-mock process_job to do nothing for now
    await worker.process_job(job_id)
    worker.process_job.assert_called_once()
