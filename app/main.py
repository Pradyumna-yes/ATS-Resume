# app/main.py
from fastapi import FastAPI
from app.api.v1.routes import router as api_router

# Try to import MongoDB init/close helpers. If motor/pymongo are not
# available or incompatible, fall back to no-op implementations so the
# app can still start for development or testing without Mongo.
try:
    from app.db.mongo import init_db, close_db
except Exception:
    async def init_db():
        return None

    def close_db():
        return None


app = FastAPI(title="ATS Resume API")
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.on_event("shutdown")
async def shutdown_event():
    close_db()
