from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from app.db.session import get_db
from app.db.models import Job, JobStatus
from sqlalchemy import update
import logging
from app.core.queue import enqueue_job

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("finish_upload_"))
async def process_finish_upload(callback: types.CallbackQuery, state: FSMContext):
    job_id = int(callback.data.split("_")[2])

    kb = [
        [
            types.InlineKeyboardButton(text="15s", callback_data=f"set_dur_{job_id}_15"),
            types.InlineKeyboardButton(text="30s", callback_data=f"set_dur_{job_id}_30"),
        ],
        [
            types.InlineKeyboardButton(text="45s", callback_data=f"set_dur_{job_id}_45"),
            types.InlineKeyboardButton(text="60s", callback_data=f"set_dur_{job_id}_60"),
        ]
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb)

    await callback.message.edit_text("Select final video duration:", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("set_dur_"))
async def process_set_duration(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    job_id = int(parts[2])
    duration = int(parts[3])

    with get_db() as session:
        session.execute(update(Job).where(Job.id == job_id).values(
            target_duration=duration,
            status=JobStatus.QUEUED
        ))
        session.commit()

    enqueue_job(job_id)

    await state.clear()
    await callback.message.edit_text(f"Duration set to {duration}s. Your video is now in the queue! 🚀 We'll notify you when it's ready.")
    await callback.answer()
