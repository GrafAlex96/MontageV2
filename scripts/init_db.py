from sqlalchemy import create_engine
from app.db.models import Base
from app.core.config import settings

def init_db():
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print("Database initialized (Sync).")

if __name__ == "__main__":
    init_db()
