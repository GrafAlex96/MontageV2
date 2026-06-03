from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.db.session import async_session
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
    async with async_session() as session:
        # Register user
        stmt = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username)
            session.add(user)
            await session.commit()

    await message.answer("Welcome to AI Video Editor! 🎬\nSend me one or more videos (up to 20) and I'll edit them for you.")

@router.message(F.video)
async def handle_video(message: types.Message, state: FSMContext, bot):
    # Get or create active job in FSM
    data = await state.get_data()
    job_id = data.get('active_job_id')

    async with async_session() as session:
        if not job_id:
            # Create new job
            stmt = select(User).where(User.telegram_id == message.from_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(telegram_id=message.from_user.id, username=message.from_user.username)
                session.add(user)
                await session.flush()

            job = Job(user_id=user.id, status=JobStatus.PENDING)
            session.add(job)
            await session.flush()
            job_id = job.id
            await state.update_data(active_job_id=job_id, file_count=0)

        file_count = data.get('file_count', 0) + 1
        if file_count > 20:
            return await message.answer("Maximum 20 videos allowed.")

        # Download video
        file_id = message.video.file_id
        file = await bot.get_file(file_id)

        file_ext = os.path.splitext(file.file_path)[1] or ".mp4"
        local_filename = f"{uuid.uuid4()}{file_ext}"
        local_path = os.path.join(settings.TEMP_STORAGE_PATH, local_filename)

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
        await session.commit()

        await state.update_data(file_count=file_count)

        kb = [
            [types.InlineKeyboardButton(text="Finish and Choose Duration", callback_data=f"finish_upload_{job_id}")]
        ]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)

        await message.answer(f"Received video {file_count}/20. Send more or click below.", reply_markup=markup)
