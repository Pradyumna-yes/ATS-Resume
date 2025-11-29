from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from app.services.storage import store_file, generate_presigned_url
from app.services.orchestrator import submit_assessment_task, create_job_from_text
import traceback

router = APIRouter()

class UploadResumeResp(BaseModel):
    resume_id: str
    filename: str
    storage_key: str
    presigned_url: str | None = None

class SubmitJobResp(BaseModel):
    job_id: str

@router.post("/upload-resume", response_model=UploadResumeResp)
async def upload_resume(file: UploadFile = File(...)):
    try:
        storage_key = await store_file(file)
        # For demonstration we return a presigned url (works when using R2/MinIO)
        presigned = generate_presigned_url(storage_key)
        resume_id = str(uuid4())
        # TODO: persist Resume DB entry (resume_id, filename, storage_key)
        return UploadResumeResp(resume_id=resume_id, filename=file.filename, storage_key=storage_key, presigned_url=presigned)
    except Exception as e:
        print(f"Error in upload_resume: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/submit-job", response_model=SubmitJobResp)
async def submit_job(source_url: Optional[str] = Form(None), text: Optional[str] = Form(None), user_id: Optional[int] = Form(None)):
    job_id = create_job_from_text(source_url, text, user_id)
    return {"job_id": job_id}

class AssessPayload(BaseModel):
    job_id: str
    resume_id: str
    config: Optional[dict] = {}

class AssessResp(BaseModel):
    assessment_id: str
    status: str

@router.post("/assess", response_model=AssessResp)
async def assess(payload: AssessPayload):
    # enqueue long-running assessment pipeline
    assessment_id = submit_assessment_task(payload.job_id, payload.resume_id, payload.config)
    return {"assessment_id": assessment_id, "status": "queued"}

@router.get("/assessment/{id}")
async def get_assessment(id: str):
    # fetch assessment results from DB
    return {"assessment_id": id, "status": "done", "results": {}}
