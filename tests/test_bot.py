import pytest
from unittest.mock import AsyncMock, MagicMock
from app.bot.handlers.upload import cmd_start, handle_video
from app.db.models import User, Job, JobStatus
from sqlalchemy import select

@pytest.mark.anyio
async def test_cmd_start():
    message = AsyncMock()
    message.from_user.id = 456
    message.from_user.username = "testuser"
    message.answer = AsyncMock()

    await cmd_start(message)
    message.answer.assert_called_once()
    assert "Welcome" in message.answer.call_args[0][0]

@pytest.mark.anyio
async def test_handle_video():
    message = AsyncMock()
    message.from_user.id = 123
    message.from_user.username = "testuser"
    message.video.file_id = "file123"
    message.video.file_size = 1000
    message.video.duration = 10
    message.video.file_name = "test.mp4"
    message.video.mime_type = "video/mp4"
    message.answer = AsyncMock()

    state = AsyncMock()
    state.get_data.return_value = {}

    bot = AsyncMock()
    bot.get_file.return_value = MagicMock(file_path="remote/path.mp4")

    await handle_video(message, state, bot)

    message.answer.assert_called_once()
    assert "Received video" in message.answer.call_args[0][0]
