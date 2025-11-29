# app/db/models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from .base import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class JobPost(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source_url = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)
    parsed_json = Column(JSON, nullable=True)
    ats_candidates = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    original_filename = Column(String)
    s3_key = Column(String, nullable=True)  # or local path
    parsed_json = Column(JSON, nullable=True)
    layout_meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    results_json = Column(JSON, nullable=True)
    score = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
