import asyncio
import os
import logging
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import Bot
from app.workers.video_worker import VideoWorker
from app.core.config import settings
from app.db.session import get_db
from app.db.models import Job, JobStatus, User, UploadedFile
from sqlalchemy import select
import uuid
import random

logging.basicConfig(level=logging.ERROR) # Suppress noise
logger = logging.getLogger("production_stress")

async def run_audit_stress_test():
    """
    Simulates various failure modes to verify production readiness.
    """
    print("\n" + "="*60)
    print("🚀 STARTING PRODUCTION HARDENING AUDIT STRESS TEST")
    print("="*60)

    # 1. TEST: LARGE FILE DELIVERY FALLBACK
    print("\n🛠️ Testing Large File Delivery Fallback...")

    with patch("app.workers.video_worker.os.path.getsize", return_value=51 * 1024 * 1024), \
         patch("app.workers.video_worker.os.path.exists", return_value=True):

        bot = MagicMock(spec=Bot)
        bot.send_document = AsyncMock()
        bot.send_video = AsyncMock()
        bot.send_message = AsyncMock()

        worker = VideoWorker(bot)

        # Setup job
        with get_db() as session:
            tg_id = random.randint(10000, 99999)
            user = User(telegram_id=tg_id, username=f"tester_{uuid.uuid4().hex[:6]}")
            session.add(user)
            session.commit()
            uid = user.id

            job = Job(user_id=uid, status=JobStatus.RENDERING, target_duration=5, trace_id=str(uuid.uuid4()))
            session.add(job)
            session.commit()
            jid = job.id

            # Need files to pass clips check
            file = UploadedFile(job_id=jid, file_path="tests/sample.mp4")
            session.add(file)
            session.commit()

            # Mock the internal parts to skip to delivery
            with patch.object(worker.renderer, 'render_final_video'), \
                 patch.object(worker.audio_service, 'improve_clarity'), \
                 patch.object(worker.subtitle_service, 'transcribe', return_value=[]), \
                 patch("app.workers.video_worker.FinalValidator.validate_output", return_value={"valid": True}):

                 await worker.process_job(jid)

                 if bot.send_document.called:
                     print("✅ SUCCESS: sendDocument used for 51MB file.")
                 else:
                     print("❌ FAILURE: sendDocument NOT used for 51MB file.")

    # 2. TEST: RENDERING FAILURE -> SIMPLE MODE RECOVERY
    print("\n🛠️ Testing Rendering Failure Recovery...")
    with patch("app.workers.video_worker.os.path.exists", return_value=True), \
         patch("app.workers.video_worker.os.path.getsize", return_value=10 * 1024 * 1024):
        with get_db() as session:
            tg_id = random.randint(10000, 99999)
            user = User(telegram_id=tg_id, username=f"tester_{uuid.uuid4().hex[:6]}")
            session.add(user)
            session.commit()
            uid = user.id

            job = Job(user_id=uid, status=JobStatus.RENDERING, target_duration=5, trace_id=str(uuid.uuid4()))
            session.add(job)
            session.commit()
            jid = job.id

            file = UploadedFile(job_id=jid, file_path="tests/sample.mp4")
            session.add(file)
            session.commit()

            bot = MagicMock(spec=Bot)
            bot.send_video = AsyncMock()
            bot.send_message = AsyncMock()
            worker = VideoWorker(bot)

            # Mock render to fail first time, then succeed
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("GPU OOM Simulation")
                return True

            with patch.object(worker.renderer, 'render_final_video', side_effect=side_effect), \
                 patch("app.workers.video_worker.FinalValidator.validate_output", return_value={"valid": True}), \
                 patch.object(worker.audio_service, 'improve_clarity'):

                 await worker.process_job(jid)

                 if call_count == 2:
                     print("✅ SUCCESS: Renderer recovered using simple_mode after failure.")
                 else:
                     print(f"❌ FAILURE: Renderer called {call_count} times.")

    print("\n" + "="*60)
    print("🏆 AUDIT STRESS TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_audit_stress_test())
