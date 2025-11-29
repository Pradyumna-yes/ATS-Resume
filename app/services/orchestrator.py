from app.tasks.worker import run_assessment_job

def create_job_from_text(source_url, text, user_id):
    # Fetch url content if provided (requests/html parser) - implement in stage A
    job_id = "job-" + uuid4().hex
    # persist JobPost DB entry with raw_text placeholder
    return job_id

def submit_assessment_task(job_id, resume_id, config):
    # enqueue Celery job
    job = run_assessment_job.delay(job_id, resume_id, config)
    # create Assessment DB entry with status queued
    return job.id
