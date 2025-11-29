# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator
from app.core.config import settings

# echo=True for dev; set False in production
_engine = create_engine(settings.DATABASE_URL, future=True, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
