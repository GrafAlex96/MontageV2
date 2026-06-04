import pytest
from unittest.mock import AsyncMock, patch
from app.services.notifications import NotificationService
from app.db.models import Job, User

@pytest.mark.anyio
async def test_send_progress_update():
    bot = AsyncMock()
    service = NotificationService(bot)

    from app.db.session import get_db
    with get_db() as session:
        user = User(telegram_id=1111, username="notif_test_unique")
        session.add(user)
        session.flush()
        job = Job(id=1010, user_id=user.id)
        session.add(job)
        session.commit()

    await service.send_progress_update(1010, 0.25)
    bot.send_message.assert_called_once()
    assert "25%" in bot.send_message.call_args[0][1]
