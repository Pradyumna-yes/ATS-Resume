# app/db/mongo.py
from typing import Optional
import os
from functools import lru_cache
from pydantic_settings import BaseSettings

# motor may be unavailable or incompatible in some environments (tests/CI).
# Import lazily and fall back gracefully so importing this module doesn't
# raise on incompatible pymongo/motor versions.
try:
    import motor.motor_asyncio as _motor_asyncio
    _MOTOR_AVAILABLE = True
except Exception:
    _motor_asyncio = None
    _MOTOR_AVAILABLE = False

class MongoSettings(BaseSettings):
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/ats_resume")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "ats_resume")

@lru_cache()
def get_mongo_settings() -> MongoSettings:
    return MongoSettings()

_mongo_client: Optional["AsyncIOMotorClient"] = None

def get_mongo_client():
    """
    Returns a cached Motor client.
    """
    global _mongo_client
    if _mongo_client is None:
        settings = get_mongo_settings()
        if not _MOTOR_AVAILABLE:
            raise RuntimeError("motor.asyncio is not available in this environment")
        _mongo_client = _motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
    return _mongo_client

def get_db():
    client = get_mongo_client()
    settings = get_mongo_settings()
    return client[settings.MONGODB_DB]
