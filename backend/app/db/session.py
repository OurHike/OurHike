"""Engine, sessionmaker, and the `get_db` FastAPI dependency.

Reads DATABASE_URL from app.config.settings - a local Postgres by default,
CI's Postgres service container under CI, Supabase's Postgres in production.
Same engine in all three. See backend/README.md.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session, closing it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
