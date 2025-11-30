# app/api/v1/presign.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import uuid
import asyncio
from app.services.r2_presign import async_generate_presigned_put_url
from app.core.config import settings
from app.api.v1.auth import get_current_user
from app.db.documents import Resume
from app.services.queue import enqueue_stream_job

router = APIRouter()

class PresignRequest(BaseModel):
    filename: str
    content_type: Optional[str] = None
    prefix: Optional[str] = "uploads/"

class PresignResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_in: int

@router.post("/presign", response_model=PresignResponse)
async def presign(req: PresignRequest, user = Depends(get_current_user)):
    """
    Return a presigned PUT URL for client to upload directly to Cloudflare R2 (S3-compatible).
    Requires authentication to tie keys to a user. If you want to allow anonymous presigns,
    remove the dependency on get_current_user (not recommended).
    """
    bucket = getattr(settings, "S3_BUCKET", None)
    if not bucket:
        raise HTTPException(status_code=500, detail="S3 bucket not configured")

    # Construct a storage key that includes user id + uuid to avoid collisions
    uid = str(user.id) if user is not None else "anonymous"
    ext = ""
    if "." in req.filename:
        ext = req.filename.split(".")[-1]
    storage_key = f"{req.prefix.rstrip('/')}/{uid}/{uuid.uuid4().hex}"
    if ext:
        storage_key = f"{storage_key}.{ext}"

    expires = 15 * 60  # 15 minutes
    upload_url = await async_generate_presigned_put_url(bucket, storage_key, expires_in=expires)

    return PresignResponse(upload_url=upload_url, storage_key=storage_key, expires_in=expires)

class ConfirmRequest(BaseModel):
    storage_key: str
    original_filename: Optional[str] = None

@router.post("/confirm-upload")
async def confirm_upload(req: ConfirmRequest, current_user = Depends(get_current_user)):
    """
    Client should call this endpoint AFTER successfully PUTing the file to the presigned URL.
    This will persist the Resume document and enqueue the pipeline job.
    """
    # Optionally: verify object exists in R2 (HEAD) before creating doc.
    resume = Resume(
        user=current_user,
        original_filename=req.original_filename or "",
        storage_key=req.storage_key
    )
    await resume.insert()

    payload = {
        "job_payload": {},
        "resume_payload": {
            "resume_id": str(resume.id),
            "storage_key": req.storage_key,
            "original_filename": req.original_filename or ""
        },
        "seed": 42
    }

    # Use resume id as idempotency key
    try:
        await enqueue_stream_job(payload, idempotency_key=str(resume.id))
    except Exception:
        # best-effort enqueue; swallow failure but consider logging/monitoring
        pass

    return {"resume_id": str(resume.id), "storage_key": req.storage_key}
