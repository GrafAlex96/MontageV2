from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.db.session import get_db
from app.db.models import User, Job, UploadedFile, JobStatus
from sqlalchemy import select
import os
from app.core.config import settings
import uuid
import logging

logger = logging.getLogger(__name__)
router = Router()

class UploadStates(StatesGroup):
    WAITING_FOR_VIDEOS = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    with get_db() as session:
        # Register user
        user = session.execute(select(User).where(User.telegram_id == message.from_user.id)).scalar_one_or_none()

        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            session.commit()

    await message.answer("Welcome to AI Video Editor! 🎬\nSend me one or more videos (up to 20) and I'll edit them for you.")

@router.message(F.video)
async def handle_video(message: types.Message, state: FSMContext, bot):
    # 1. Strict Validation
    if not message.video or message.video.mime_type not in ['video/mp4', 'video/quicktime', 'video/x-matroska']:
        return await message.answer("Unsupported file format. Please send MP4, MOV or MKV.")

    max_size_bytes = settings.MAX_VIDEO_SIZE_GB * 1024 * 1024 * 1024
    if message.video.file_size > max_size_bytes:
        return await message.answer(f"File is too large. Maximum size is {settings.MAX_VIDEO_SIZE_GB}GB.")

    with get_db() as session:
        # ALWAYS fetch user first to avoid UnboundLocalError and ensure we have fresh data
        user = session.execute(select(User).where(User.telegram_id == message.from_user.id)).scalar_one_or_none()
        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            session.flush()

        # Get or create active job
        data = await state.get_data()
        job_id = data.get('active_job_id')

        # Concurrent job protection: Only allow one job to be in the "QUEUED" to "POST_PROCESSING" phase.
        # However, we must allow the CURRENT PENDING job to continue accepting uploads.
        if job_id:
             # Check if this user has ANOTHER job that is already processing
             other_active_job = session.execute(
                select(Job).where(
                    Job.user_id == user.id,
                    Job.id != job_id,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.ANALYZING, JobStatus.PROCESSING, JobStatus.RENDERING, JobStatus.POST_PROCESSING])
                )
             ).scalar_one_or_none()

             if other_active_job:
                 return await message.answer("You already have a job in progress. Please wait for it to finish! ⏳")

        if not job_id:
            job = Job(user_id=user.id, status=JobStatus.PENDING)
            session.add(job)
            session.flush()
            job_id = job.id
            await state.update_data(active_job_id=job_id)
            logger.info("JOB_CREATED", extra={"job_id": job_id, "user_id": user.id})

        # Source of truth for file count is DB
        from sqlalchemy import func
        file_count = session.execute(
            select(func.count(UploadedFile.id)).where(UploadedFile.job_id == job_id)
        ).scalar() or 0
        file_count += 1

        if file_count > settings.MAX_CLIPS_PER_JOB:
            return await message.answer(f"Maximum {settings.MAX_CLIPS_PER_JOB} videos allowed in SAFE MODE.")

        # 2. Path Traversal Protection
        file_id = message.video.file_id
        file = await bot.get_file(file_id)

        # Use UUID to prevent path traversal
        file_ext = os.path.splitext(file.file_path)[1] or ".mp4"
        if not file_ext.lower() in ['.mp4', '.mov', '.mkv']:
             file_ext = ".mp4"

        local_filename = f"{uuid.uuid4()}{file_ext}"
        # Ensure path is strictly inside temp storage
        local_path = os.path.abspath(os.path.join(settings.TEMP_STORAGE_PATH, local_filename))
        if not local_path.startswith(os.path.abspath(settings.TEMP_STORAGE_PATH)):
            raise ValueError("Potential path traversal attack detected")

        # 3. User Quota Check
        if user.used_storage_bytes + message.video.file_size > user.storage_quota_bytes:
             return await message.answer("Storage quota exceeded. Please delete some videos first.")

        # Update used storage
        user.used_storage_bytes += message.video.file_size
        session.add(user) # Explicitly mark for update

        await bot.download_file(file.file_path, local_path)

        # Save to DB
        uploaded_file = UploadedFile(
            job_id=job_id,
            file_path=local_path,
            file_name=message.video.file_name or "video.mp4",
            file_size=message.video.file_size,
            duration=message.video.duration
        )
        session.add(uploaded_file)
        session.commit()

        logger.info(
            "VIDEO_RECEIVED",
            extra={
                "job_id": job_id,
                "user_id": message.from_user.id,
                "file_path": local_path,
                "file_size": message.video.file_size
            }
        )

        await state.update_data(file_count=file_count)

        kb = [
            [types.InlineKeyboardButton(text="Finish and Choose Duration", callback_data=f"finish_upload_{job_id}")]
        ]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)

        await message.answer(f"Received video {file_count}/20. Send more or click below.", reply_markup=markup)
