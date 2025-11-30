# app/api/v1/pipeline_routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.pipeline import run_assessment_pipeline
from app.db.documents import Assessment
from app.db.mongo import get_db

router = APIRouter()

class AssessRequest(BaseModel):
    job_id: Optional[str] = None
    resume_id: Optional[str] = None
    # allow direct payloads for tests/demo
    job_payload: Optional[dict] = None
    resume_payload: Optional[dict] = None
    seed: int = 42

@router.post("/assess")
async def assess(payload: AssessRequest):
    # For demo/tests: accept job_payload/resume_payload directly if present.
    # When only an id is provided, try Beanie's `get()` first and fall
    # back to a tolerant direct DB lookup (useful for in-memory shims
    # that store string `_id` values).
    if payload.job_payload is None and payload.job_id:
        job_payload = {}
        try:
            JobPosting = __import__("app.db.documents", fromlist=["JobPosting"]).JobPosting
            job = await JobPosting.get(payload.job_id)
            if job:
                job_payload = job.dict() if hasattr(job, "dict") else job
        except Exception:
            # Fallback: direct DB lookup by _id (works with in-memory shim)
            try:
                db = get_db()
                job = await db["jobposting"].find_one({"_id": payload.job_id})
                if job:
                    job_payload = job
            except Exception:
                pass
    else:
        job_payload = payload.job_payload or {}

    if payload.resume_payload is None and payload.resume_id:
        resume_payload = {}
        try:
            Resume = __import__("app.db.documents", fromlist=["Resume"]).Resume
            resume = await Resume.get(payload.resume_id)
            if resume:
                resume_payload = resume.dict() if hasattr(resume, "dict") else resume
        except Exception:
            # Fallback: direct DB lookup by _id (works with in-memory shim)
            try:
                db = get_db()
                resume = await db["resume"].find_one({"_id": payload.resume_id})
                if resume:
                    resume_payload = resume
            except Exception:
                pass
    else:
        resume_payload = payload.resume_payload or {}

    result = await run_assessment_pipeline(job_payload, resume_payload, seed=payload.seed)
    return result

@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str):
    a = await Assessment.get(assessment_id)
    if not a:
        raise HTTPException(404, "Not found")
    return a
