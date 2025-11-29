# app/db/mongo.py
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.db.documents import User, Resume, JobPosting, Assessment, History

mongo_client: AsyncIOMotorClient | None = None

async def init_db():
    global mongo_client
    if mongo_client:
        return
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    # Use the DB name from the URI or fall back to `ats_resume`
    db = mongo_client.get_default_database() if mongo_client.get_default_database() else mongo_client["ats_resume"]
    await init_beanie(database=db, document_models=[User, Resume, JobPosting, Assessment, History])

def get_client() -> AsyncIOMotorClient | None:
    return mongo_client

def get_database():
    if mongo_client:
        return mongo_client.get_default_database()
    return None

def close_db():
    global mongo_client
    if mongo_client:
        mongo_client.close()
        mongo_client = None
