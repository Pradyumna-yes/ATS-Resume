# app/repositories/assessments.py
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.db.mongo import get_db
from app.models.assessment import AssessmentCreate, AssessmentInDB, AssessmentListItem, HistoryItem
import uuid

ASSESSMENTS_COLLECTION = "assessments"
HISTORY_COLLECTION = "assessment_history"

def _now():
    return datetime.utcnow()

def _to_id(doc):
    # convert Mongo's _id (ObjectId) to str when returning
    if not doc:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

async def create_assessment(obj: AssessmentCreate) -> str:
    db = get_db()
    payload = {
        "user_id": obj.user_id,
        "job_id": obj.job_id,
        "resume_id": obj.resume_id,
        "final_score": float(obj.final_score),
        "results": obj.results,
        "metadata": obj.metadata or {},
        "created_at": _now(),
        "updated_at": _now(),
    }
    res = await db[ASSESSMENTS_COLLECTION].insert_one(payload)
    return str(res.inserted_id)

async def get_assessment(assessment_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db[ASSESSMENTS_COLLECTION].find_one({"_id": {"$oid": assessment_id}})  # try ObjectId-like first
    if not doc:
        # fallback to try string id stored as str _id
        doc = await db[ASSESSMENTS_COLLECTION].find_one({"_id": assessment_id})
    if not doc:
        # also try matching by string id field (if created differently)
        doc = await db[ASSESSMENTS_COLLECTION].find_one({"id": assessment_id})
    if not doc:
        return None
    out = _to_id(doc)
    return out

async def get_assessment_by_oid(oid) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db[ASSESSMENTS_COLLECTION].find_one({"_id": oid})
    return _to_id(doc) if doc else None

async def list_assessments(user_id: Optional[str]=None, limit:int=20, skip:int=0) -> List[Dict[str,Any]]:
    db = get_db()
    query = {}
    if user_id:
        query["user_id"] = user_id
    cur = db[ASSESSMENTS_COLLECTION].find(query).sort("created_at",-1).skip(skip).limit(limit)
    out = []
    async for d in cur:
        out.append(_to_id(d))
    return out

async def delete_assessment(assessment_id: str) -> bool:
    db = get_db()
    res = await db[ASSESSMENTS_COLLECTION].delete_one({"_id": {"$oid": assessment_id}})
    if res.deleted_count == 0:
        res = await db[ASSESSMENTS_COLLECTION].delete_one({"_id": assessment_id})
    return res.deleted_count > 0

async def append_history(assessment_id: str, old_score: Optional[float], new_score: Optional[float], diff: Optional[Dict[str,Any]]=None) -> str:
    db = get_db()
    payload = {
        "assessment_id": assessment_id,
        "old_score": old_score,
        "new_score": new_score,
        "diff": diff or {},
        "created_at": _now()
    }
    res = await db[HISTORY_COLLECTION].insert_one(payload)
    return str(res.inserted_id)

async def list_history(assessment_id: str, limit:int=50) -> List[Dict[str,Any]]:
    db = get_db()
    cur = db[HISTORY_COLLECTION].find({"assessment_id": assessment_id}).sort("created_at",-1).limit(limit)
    out = []
    async for d in cur:
        out.append(_to_id(d))
    return out
