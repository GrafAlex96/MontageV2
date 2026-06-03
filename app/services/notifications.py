from aiogram import Bot
import logging
from app.db.session import get_db
from app.db.models import Job, User
from sqlalchemy import select

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_progress_update(self, job_id: int, progress: float):
        """Send a message to the user about their job progress."""
        with get_db() as session:
            item = session.execute(select(Job, User).join(User).where(Job.id == job_id)).fetchone()
            if not item:
                return

            job, user = item

            progress_pct = int(progress * 100)
            message = f"Processing your video: {progress_pct}% complete..."

            try:
                # We could keep track of message_id to edit instead of sending new ones
                # For now, let's just log it or send if it's a major milestone
                if progress_pct % 25 == 0 or progress_pct == 10:
                    await self.bot.send_message(user.telegram_id, message)
            except Exception as e:
                logger.error(f"Failed to send progress update: {e}")

    async def notify_error(self, job_id: int, error: str):
        with get_db() as session:
            user = session.execute(select(User).join(Job).where(Job.id == job_id)).scalar_one_or_none()
            if user:
                await self.bot.send_message(user.telegram_id, f"❌ Error processing your video: {error}")
