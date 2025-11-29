from sqlalchemy import Column, Integer, String, Float, JSON
from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class JobPosting(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    source_url = Column(String, nullable=True)
    raw_text = Column(String, nullable=True)


class Resume(Base):
    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    original_filename = Column(String)
    storage_key = Column(String)


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    job_id = Column(Integer)
    resume_id = Column(Integer)
    score = Column(Float)
    results_json = Column(JSON)
