# app/models/assessment.py
from pydantic import BaseModel, Field, Json
from typing import Optional, Any, Dict, List
from datetime import datetime
from bson import ObjectId

# Small helper to coerce ObjectId to str in responses
def oid_str(oid):
    try:
        return str(oid)
    except Exception:
        return None

class StageResult(BaseModel):
    # Generic container for any stage output
    name: str
    payload: Dict[str, Any] = Field(default_factory=dict)

class AssessmentCreate(BaseModel):
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    resume_id: Optional[str] = None
    final_score: float = 0.0
    results: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None

class AssessmentInDB(BaseModel):
    id: str
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    resume_id: Optional[str] = None
    final_score: float = 0.0
    results: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

class AssessmentListItem(BaseModel):
    id: str
    final_score: float
    role_title: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime

class HistoryItem(BaseModel):
    id: str
    assessment_id: str
    old_score: Optional[float] = None
    new_score: Optional[float] = None
    diff: Optional[Dict[str, Any]] = None
    created_at: datetime
