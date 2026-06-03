import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
from app.core.config import settings

async def init_db():
    # We need to change the URL to synchronous for initialization if using sqlite
    # OR we can just use the async engine
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized.")

if __name__ == "__main__":
    asyncio.run(init_db())
