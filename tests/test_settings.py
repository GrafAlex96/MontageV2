import pytest
from unittest.mock import AsyncMock
from app.bot.handlers.settings import process_finish_upload, process_set_duration
from app.db.models import Job, User
from sqlalchemy import select

@pytest.mark.anyio
async def test_process_finish_upload():
    callback = AsyncMock()
    callback.data = "finish_upload_1"
    callback.message.edit_text = AsyncMock()
    state = AsyncMock()

    await process_finish_upload(callback, state)
    callback.message.edit_text.assert_called_once()
    assert "Select final video duration" in callback.message.edit_text.call_args[0][0]

@pytest.mark.anyio
async def test_process_set_duration():
    callback = AsyncMock()
    callback.data = "set_dur_1_30"
    callback.message.edit_text = AsyncMock()
    state = AsyncMock()

    from app.db.session import get_db
    with get_db() as session:
        # Create a user and job first
        user = User(telegram_id=789, username="dur_test")
        session.add(user)
        session.flush()
        job = Job(id=100, user_id=user.id) # Use higher ID to avoid conflict
        session.add(job)
        session.commit()

    callback.data = "set_dur_100_30"
    await process_set_duration(callback, state)

    with get_db() as session:
        stmt = select(Job).where(Job.id == 100)
        res = session.execute(stmt)
        job = res.scalar_one()
        assert job.target_duration == 30

    callback.message.edit_text.assert_called_once()
    assert "Duration set to 30s" in callback.message.edit_text.call_args[0][0]
