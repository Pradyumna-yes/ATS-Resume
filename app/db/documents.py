"""Beanie document models used for MongoDB-backed tests.

These are lightweight documents that mirror the SQLAlchemy models
used elsewhere; they exist so tests that initialize Beanie can run.
"""
from typing import Optional, Any
from beanie import Document


class User(Document):
    email: str
    password_hash: str


class Resume(Document):
    user_id: Optional[str] = None
    original_filename: Optional[str] = None
    storage_key: Optional[str] = None


class JobPosting(Document):
    user_id: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: Optional[str] = None


class Assessment(Document):
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    resume_id: Optional[str] = None
    score: Optional[float] = None
    results_json: Optional[dict[Any, Any]] = None


class History(Document):
    item_id: Optional[str] = None
    action: Optional[str] = None
    timestamp: Optional[str] = None

