# tests/conftest.py
import pytest
import asyncio

# motor / beanie are optional for running non-db tests. Import lazily
# and mark availability so we can skip DB fixtures if the environment
# has an incompatible motor/pymongo combination.
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from beanie import init_beanie
    _MOTOR_AVAILABLE = True
except Exception:
    AsyncIOMotorClient = None
    init_beanie = None
    _MOTOR_AVAILABLE = False

from app.db.documents import User, Resume, JobPosting, Assessment, History
from app.core.config import settings

@pytest.fixture(scope="session")
def event_loop():
    return asyncio.get_event_loop()

@pytest.fixture(autouse=True)
def mock_get_current_user(monkeypatch):
    """Auto-mock auth for all tests so routes don't require real tokens."""
    class TestUser:
        def __init__(self):
            self.id = "test-user-id"
            self.email = "test@example.com"
    
    class TokenData:
        def __init__(self):
            self.sub = "test-user-id"
    
    test_user = TestUser()
    token_data = TokenData()
    
    # Mock decode_access_token to accept any token in tests
    from app.services import auth as auth_service
    monkeypatch.setattr(auth_service, "decode_access_token", lambda token: token_data)
    
    # Mock get_current_user to return test user
    from app.api.v1 import auth as auth_api
    monkeypatch.setattr(auth_api, "get_current_user", lambda credentials=None: test_user)

@pytest.fixture(scope="function")
async def test_db():
    if not _MOTOR_AVAILABLE:
        pytest.skip("motor/beanie not available or incompatible — skipping DB tests")

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client.get_default_database()
    await init_beanie(database=db, document_models=[User, Resume, JobPosting, Assessment, History])
    # optionally drop collections to start clean
    for name in ["users", "resumes", "jobs", "assessments", "history"]:
        await db.drop_collection(name)
    yield db
    # cleanup - drop test collections
    for name in ["users", "resumes", "jobs", "assessments", "history"]:
        await db.drop_collection(name)
    client.close()
