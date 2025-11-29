# app/api/v1/crud_routes.py
from fastapi import APIRouter, HTTPException
from app.api.v1.schemas import JobCreate, JobResp, ResumeCreate, ResumeResp, AssessmentCreate, AssessmentResp
from app.db.documents import JobPosting, Resume, Assessment
from typing import Optional
from pydantic import BaseModel
from beanie.exceptions import CollectionWasNotInitialized
from uuid import uuid4

router = APIRouter()

# Simple in-memory fallback store used when Beanie/collection is not initialized
_INMEM_STORE = {
    "jobs": {},
    "resumes": {},
    "assessments": {},
}

@router.post("/jobs", response_model=JobResp)
async def create_job(payload: JobCreate):
    try:
        job = JobPosting(source_url=str(payload.source_url) if payload.source_url else None, raw_text=payload.raw_text)
        await job.insert()
        return JobResp.from_orm(job)
    except CollectionWasNotInitialized:
        jid = str(uuid4())
        _INMEM_STORE["jobs"][jid] = {"id": jid, "source_url": str(payload.source_url) if payload.source_url else None, "raw_text": payload.raw_text}
        return _INMEM_STORE["jobs"][jid]

@router.get("/jobs/{job_id}", response_model=JobResp)
async def get_job(job_id: str):
    try:
        job = await JobPosting.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobResp.from_orm(job)
    except Exception:
        # Fall back to in-memory store if Beanie isn't initialized or if the
        # document id can't be parsed (e.g. UUID used instead of ObjectId).
        j = _INMEM_STORE["jobs"].get(job_id)
        if not j:
            raise HTTPException(status_code=404, detail="Job not found")
        return j

@router.post("/resumes/db-save", response_model=ResumeResp)
async def create_resume(payload: ResumeCreate):
    try:
        resume = Resume(original_filename=payload.original_filename, storage_key=payload.storage_key)
        await resume.insert()
        return ResumeResp.from_orm(resume)
    except CollectionWasNotInitialized:
        rid = str(uuid4())
        _INMEM_STORE["resumes"][rid] = {"id": rid, "original_filename": payload.original_filename, "storage_key": payload.storage_key}
        return _INMEM_STORE["resumes"][rid]

@router.get("/resumes/{resume_id}", response_model=ResumeResp)
async def get_resume(resume_id: str):
    try:
        resume = await Resume.get(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        return ResumeResp.from_orm(resume)
    except Exception:
        r = _INMEM_STORE["resumes"].get(resume_id)
        if not r:
            raise HTTPException(status_code=404, detail="Resume not found")
        return r

@router.post("/assessments/create", response_model=AssessmentResp)
async def create_assessment(payload: AssessmentCreate):
    try:
        a = Assessment(job=payload.job_id, resume=payload.resume_id, user=payload.user_id)
        await a.insert()
        return AssessmentResp.from_orm(a)
    except CollectionWasNotInitialized:
        aid = str(uuid4())
        _INMEM_STORE["assessments"][aid] = {"id": aid, "score": None, "results_json": None}
        return _INMEM_STORE["assessments"][aid]

@router.get("/assessments/{assessment_id}", response_model=AssessmentResp)
async def get_assessment(assessment_id: str):
    try:
        a = await Assessment.get(assessment_id)
        if not a:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return AssessmentResp.from_orm(a)
    except Exception:
        a = _INMEM_STORE["assessments"].get(assessment_id)
        if not a:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return a
