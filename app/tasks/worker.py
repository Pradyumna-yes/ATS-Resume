from celery import Celery
from app.services.llm_client import run_stage
from app.db.session import SessionLocal

celery = Celery(__name__, broker="redis://redis:6379/0")

@celery.task(bind=True)
def run_assessment_job(self, job_id, resume_id, config):
    # Step: Load job & resume raw data from DB
    # Stage A: JD Normalizer & ATS Detector
    stage_a_output = run_stage("stage_a", {"job_id": job_id}, config)
    # Stage B: JD Extractor
    stage_b_output = run_stage("stage_b", stage_a_output, config)
    # Stage C: Resume Parser
    stage_c_output = run_stage("stage_c", {"resume_id": resume_id}, config)
    # Stage D: Matcher & Scorer
    stage_d_output = run_stage("stage_d", {"jd": stage_b_output, "resume": stage_c_output}, config)
    # Stage E: Recommendation Generator
    stage_e_output = run_stage("stage_e", stage_d_output, config)
    # Persist assessment results, score, etc.
    return {"status":"completed", "score": stage_d_output.get("score")}
