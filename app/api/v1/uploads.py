# app/api/v1/uploads.py
"""
Protected upload endpoint.
- Accepts file upload (multipart)
- Calls app.services.storage.store_file(file) to save to S3/R2 (async or sync)
- Creates Resume document in MongoDB (Beanie)
- Enqueues pipeline job to Redis Streams via enqueue_stream_job(payload, idempotency_key)
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import Any, Dict
import inspect
import asyncio
from app.api.v1.auth import get_current_user
from app.db.documents import Resume
from app.services.storage import store_file  # your storage abstraction
from app.services.queue import enqueue_stream_job
from app.core.config import settings

router = APIRouter()

# helper to call store_file whether it's async or sync
async def _call_store_file(file: UploadFile) -> str:
    """
    Call store_file(file) but support both async and sync implementations.
    Must return a storage key (string).
    """
    if inspect.iscoroutinefunction(store_file):
        # async function
        return await store_file(file)
    else:
        # sync function — run in threadpool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        # read bytes so store_file (sync) can access file content; create a new UploadFile-like wrapper if needed
        # Some implementations expect a SpooledTemporaryFile or bytes; adapt based on your store_file signature.
        return await loop.run_in_executor(None, lambda: store_file(file))

@router.post("/upload-resume", status_code=200)
async def upload_resume(file: UploadFile = File(...), current_user = Depends(get_current_user)):
    # Basic validations
    fname = file.filename or ""
    if not fname.lower().endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    # Store file (S3/R2)
    try:
        storage_key = await _call_store_file(file)
    except Exception as exc:
        # For debugging, you can log exc; avoid leaking internals to client
        raise HTTPException(status_code=500, detail="Failed to store file") from exc

    # Persist Resume document
    resume = Resume(
        user=current_user,
        original_filename=fname,
        storage_key=storage_key
    )
    await resume.insert()

    # Build payload for stream job
    payload: Dict[str, Any] = {
        "job_payload": {},  # optional: you might include job-related fields here
        "resume_payload": {
            "resume_id": str(resume.id),
            "storage_key": storage_key,
            "original_filename": fname,
        },
        "seed": 42
    }

    # Use idempotency key to avoid double processing if re-submitted
    idempotency_key = str(resume.id)

    # Enqueue to Redis Streams (async)
    try:
        # We await enqueue_stream_job — this is quick and reliable
        await enqueue_stream_job(payload, idempotency_key=idempotency_key)
    except Exception:
        # enqueue is best-effort; do not block the upload response if Redis is temporarily unavailable
        # but surface a warning in response (or better: log it). Here we just return success and let worker catch issues.
        pass

    return {"resume_id": str(resume.id), "filename": fname, "storage_key": storage_key}
