# app/api/v1/pipeline_routes.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.pipeline import run_assessment_pipeline
from app.db.documents import Assessment

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
    # For demo: accept job_payload/resume_payload directly if present
    if payload.job_payload is None and payload.job_id:
        job = await (await __import__("app.db.documents", fromlist=["JobPosting"]).JobPosting.get(payload.job_id))
        if job:
            job_payload = job.dict()
        else:
            raise HTTPException(404, "Job not found")
    else:
        job_payload = payload.job_payload or {}

    if payload.resume_payload is None and payload.resume_id:
        resume = await (await __import__("app.db.documents", fromlist=["Resume"]).Resume.get(payload.resume_id))
        if resume:
            resume_payload = resume.dict()
        else:
            raise HTTPException(404, "Resume not found")
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
