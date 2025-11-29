# app/api/v1/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class UploadResumeResp(BaseModel):
    resume_id: str
    filename: str
    storage_key: str
    presigned_url: Optional[str] = None

class SubmitJobResp(BaseModel):
    job_id: str

class AssessPayload(BaseModel):
    job_id: str
    resume_id: str
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)

class AssessResp(BaseModel):
    assessment_id: str
    status: str

class AssessmentResult(BaseModel):
    assessment_id: str
    score: Optional[float]
    results: Optional[Dict[str, Any]] = None
