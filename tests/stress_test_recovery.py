import asyncio
import os
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Job, User, UploadedFile, JobStatus
from app.core.config import settings
from app.workers.video_worker import VideoWorker
from unittest.mock import AsyncMock

logging.basicConfig(level=logging.INFO)

async def test_failure_recovery():
    print("\n--- Test Suite 5: Failure Recovery ---")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    bot = AsyncMock()
    worker = VideoWorker(bot)

    with Session() as session:
        # 1. Invalid file
        print("Testing invalid file...")
        user = session.execute(select(User).limit(1)).scalar()
        job = Job(user_id=user.id, target_duration=15, status=JobStatus.PENDING)
        session.add(job)
        session.commit()

        up = UploadedFile(job_id=job.id, file_path="non_existent.mp4")
        session.add(up)
        session.commit()

        await worker.process_job(job.id)

        session.refresh(job)
        print(f"Job Status: {job.status}, Error: {job.error_message}")

if __name__ == "__main__":
    asyncio.run(test_failure_recovery())
