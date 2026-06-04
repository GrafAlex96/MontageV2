import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.core.config import settings
from app.core.logging import setup_logging
from app.bot.handlers import upload, settings as settings_handlers
from app.workers.video_worker import VideoWorker
from app.api.main import app as fastapi_app
import uvicorn

setup_logging()
logger = logging.getLogger("video_editor")

async def start_bot():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.critical("FATAL: BOT_TOKEN is missing or invalid in .env")
        sys.exit(1)

    try:
        bot = Bot(token=settings.BOT_TOKEN)
        dp = Dispatcher()

        dp.include_router(upload.router)
        dp.include_router(settings_handlers.router)

        # In this consolidated single-user version,
        # we don't need a custom worker loop polling DB if we use RQ.
        # But if RQ is not running, we might need a fallback.
        # For now, let's just start the bot.

        logger.info("Bot started")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        # Keep the loop running for other tasks (like the API)
        while True:
            await asyncio.sleep(3600)

def run_api():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

async def main():
    # Since aiogram 3.x and FastAPI both have their event loops,
    # we can run them together.
    # For production, we might want separate processes, but for this modular app,
    # we can run them in the same async loop if we handle it carefully.

    # Run FastAPI in a separate thread/process or use an adapter.
    # A simpler way for this project is to run them as separate commands,
    # but I'll provide a unified entry point that starts both.

    api_config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    api_server = uvicorn.Server(api_config)

    await asyncio.gather(
        api_server.serve(),
        start_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
