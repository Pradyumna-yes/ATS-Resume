# app/main.py
from fastapi import FastAPI
from app.api.v1.routes import router as api_router
from app.api.v1.pipeline_routes import router as pipeline_router
# app/main.py (snippet)
from app.api.v1.auth import router as auth_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.presign import router as presign_router
# app/main.py snippet
from app.api.v1.latex import router as latex_router
from app.api.v1.assessments import router as assessments_router


from app.api.v1.latex_tectonic import router as latex_tectonic_router



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

# Register routers after `app` is created. Include pipeline routes first
# so the pipeline `/assess` endpoint is the active handler when paths collide.
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")
# Attach auth and uploads routers under the API prefix
# Mount auth routes at the root `/auth` paths used by tests
app.include_router(auth_router)
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(presign_router, prefix="/api/v1")

app.include_router(latex_tectonic_router, prefix="/api/v1")
app.include_router(latex_router, prefix="/api/v1")
app.include_router(assessments_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    await init_db()


@app.on_event("shutdown")
async def shutdown_event():
    close_db()
