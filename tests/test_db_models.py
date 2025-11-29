# tests/test_db_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db import models
from app.db.models import User, Resume, JobPosting, Assessment
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal

def test_create_user_resume_job_assessment(in_memory_db):
    db = in_memory_db()
    with db.begin():
        user = User(email="jane@example.com", password_hash="hashedpw")
        db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None

    # create job
    job = JobPosting(user_id=user.id, raw_text="Data Analyst JD")
    db.add(job)
    db.commit()
    db.refresh(job)
    assert job.id is not None

    # create resume
    resume = Resume(user_id=user.id, original_filename="jane.pdf", storage_key="key123")
    db.add(resume)
    db.commit()
    db.refresh(resume)
    assert resume.id is not None

    # create assessment
    ass = Assessment(user_id=user.id, job_id=job.id, resume_id=resume.id, score=75.0, results_json={"skills":10})
    db.add(ass)
    db.commit()
    db.refresh(ass)
    assert ass.id is not None
    assert ass.score == 75.0
