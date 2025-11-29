# app/api/v1/schemas.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any

class JobCreate(BaseModel):
    source_url: Optional[HttpUrl] = None
    raw_text: Optional[str] = None
    user_id: Optional[str] = None

class JobResp(BaseModel):
    id: str
    source_url: Optional[str]
    raw_text: Optional[str]

    class Config:
        orm_mode = True

class ResumeCreate(BaseModel):
    user_id: Optional[str] = None
    original_filename: Optional[str] = None
    storage_key: Optional[str] = None

class ResumeResp(BaseModel):
    id: str
    original_filename: Optional[str]
    storage_key: Optional[str]
    class Config:
        orm_mode = True

class AssessmentCreate(BaseModel):
    job_id: str
    resume_id: str
    user_id: Optional[str] = None

class AssessmentResp(BaseModel):
    id: str
    score: Optional[float]
    results_json: Optional[Dict[str, Any]] = None
    class Config:
        orm_mode = True
