
import os
import asyncio
import logging
from aiogram import Bot
from app.workers.video_worker import VideoWorker
from app.core.config import settings
from app.db.session import get_db
from app.db.models import Job, JobStatus, User, UploadedFile
from sqlalchemy import insert, select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fallback_test")

async def test_fallback_pipeline():
    """
    Simulates a job where SMART analysis is forced to fail (or RAM is low)
    to verify the Fallback Pipeline Guarantee.
    """
    print("\n" + "="*50)
    print("🚀 STARTING FALLBACK PIELINE STRESS TEST")
    print("="*50)

    # 1. Setup Mock Job in DB
    with get_db() as session:
        # Ensure user exists
        user = session.execute(select(User).where(User.telegram_id == 12345)).scalar_one_or_none()
        if not user:
            user = User(telegram_id=12345, username="test_user")
            session.add(user)
            session.commit()
            session.refresh(user)

        # Create Job
        import uuid
        job = Job(
            user_id=user.id,
            status=JobStatus.PENDING,
            target_duration=4, # 4 seconds (sample is 5s)
            trace_id=f"test-fallback-{uuid.uuid4()}"
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # Add a dummy file (using the existing sample.mp4 if available, or any mp4)
        sample_path = os.path.abspath("tests/sample.mp4")
        if not os.path.exists(sample_path):
             print(f"❌ Sample file missing at {sample_path}. Run a test that generates it first.")
             return

        file = UploadedFile(job_id=job.id, file_path=sample_path)
        session.add(file)
        session.commit()

        job_id = job.id

    # 2. Configure Settings for "Failure" or "Safe Mode"
    # We can force SAFE_MODE = True and set a tiny RAM budget
    settings.SAFE_MODE = True
    settings.MAX_RAM_MB = 100 # Very low, should trigger SAFE MODE behaviors

    # 3. Run Worker
    bot = Bot(token="123:ABC") # Dummy token, we will mock send_video
    worker = VideoWorker(bot)

    # Mock bot.send_video and bot.send_message to avoid actual Telegram calls
    async def mock_send_video(*args, **kwargs):
        print("✅ SUCCESS: Worker attempted to deliver video!")
        return type('obj', (object,), {'message_id': 1})

    async def mock_send_message(*args, **kwargs):
        print(f"💬 Bot Message: {args[1] if len(args)>1 else kwargs.get('text')}")
        return True

    worker.bot.send_video = mock_send_video
    worker.bot.send_message = mock_send_message

    print(f"🛠️ Processing Job {job_id} with Forced Safe Mode...")

    try:
        await worker.process_job(job_id)
    except Exception as e:
        print(f"❌ Worker crashed: {e}")

    # 4. Verify Result
    with get_db() as session:
        final_job = session.execute(select(Job).where(Job.id == job_id)).scalar_one()
        print(f"\nFinal Job Status: {final_job.status}")
        if final_job.status == JobStatus.COMPLETED:
            print("🏆 TEST PASSED: Pipeline completed despite low-RAM/Safe-mode settings.")
        else:
            print(f"💀 TEST FAILED: Job status is {final_job.status}. Error: {final_job.error_message}")

if __name__ == "__main__":
    asyncio.run(test_fallback_pipeline())
