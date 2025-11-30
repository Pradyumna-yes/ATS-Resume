# app/api/v1/assessments.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from pydantic import BaseModel
from app.repositories.assessments import create_assessment, get_assessment, list_assessments, delete_assessment, append_history, list_history
from app.models.assessment import AssessmentCreate, AssessmentInDB, AssessmentListItem, HistoryItem
from datetime import datetime

router = APIRouter()

class CreateAssessmentResp(BaseModel):
    assessment_id: str

@router.post("/assess", response_model=CreateAssessmentResp)
async def post_assess(payload: AssessmentCreate):
    """
    Persist an assessment. Usually pipeline.run_assessment_pipeline will call repository directly
    but we expose this endpoint for completeness (and for tests).
    """
    aid = await create_assessment(payload)
    return {"assessment_id": aid}

@router.get("/assessment/{assessment_id}")
async def get_assessment_route(assessment_id: str):
    doc = await get_assessment(assessment_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return doc

@router.get("/assessments")
async def get_assessments_route(user_id: Optional[str] = Query(None), limit: int = Query(20), skip: int = Query(0)):
    rows = await list_assessments(user_id, limit=limit, skip=skip)
    return {"items": rows, "count": len(rows)}

@router.delete("/assessment/{assessment_id}")
async def delete_assessment_route(assessment_id: str):
    ok = await delete_assessment(assessment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found or already deleted")
    return {"deleted": True}

@router.get("/assessment/{assessment_id}/history")
async def get_assessment_history(assessment_id: str):
    rows = await list_history(assessment_id)
    return {"items": rows}
