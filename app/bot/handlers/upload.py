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

    if message.video.file_size > 2 * 1024 * 1024 * 1024: # 2GB
        return await message.answer("File is too large. Maximum size is 2GB.")

    # Get or create active job in FSM
    data = await state.get_data()
    job_id = data.get('active_job_id')

    with get_db() as session:
        if not job_id:
            # Create new job
            user = session.execute(select(User).where(User.telegram_id == message.from_user.id)).scalar_one_or_none()

            if not user:
                user = User(telegram_id=message.from_user.id, username=message.from_user.username)
                session.add(user)
                session.flush()

            job = Job(user_id=user.id, status=JobStatus.PENDING)
            session.add(job)
            session.flush()
            job_id = job.id
            await state.update_data(active_job_id=job_id, file_count=0)

        file_count = data.get('file_count', 0) + 1
        if file_count > 20:
            return await message.answer("Maximum 20 videos allowed.")

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
        user = session.execute(select(User).where(User.id == user.id)).scalar_one()
        if user.used_storage_bytes + message.video.file_size > user.storage_quota_bytes:
             return await message.answer("Storage quota exceeded. Please delete some videos first.")

        # Update used storage
        user.used_storage_bytes += message.video.file_size

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

        await state.update_data(file_count=file_count)

        kb = [
            [types.InlineKeyboardButton(text="Finish and Choose Duration", callback_data=f"finish_upload_{job_id}")]
        ]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)

        await message.answer(f"Received video {file_count}/20. Send more or click below.", reply_markup=markup)
