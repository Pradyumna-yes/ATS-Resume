# scripts/smoke_test.py
import requests
import json
import sys
from pprint import pprint

BASE = "http://127.0.0.1:8000"
HEADERS = {"Content-Type": "application/json"}

def post_job():
    payload = {"raw_text": "Sample JD: Data Analyst - SQL, Power BI, 3+ years"}
    r = requests.post(f"{BASE}/api/v1/jobs", headers=HEADERS, json=payload, timeout=10)
    print("POST /api/v1/jobs ->", r.status_code)
    pprint(r.json())
    return r.json()

def post_resume():
    payload = {"original_filename": "test_resume.pdf", "storage_key": "fake-key-1234.pdf"}
    r = requests.post(f"{BASE}/api/v1/resumes/db-save", headers=HEADERS, json=payload, timeout=10)
    print("POST /api/v1/resumes/db-save ->", r.status_code)
    pprint(r.json())
    return r.json()

def get_job(job_id):
    r = requests.get(f"{BASE}/api/v1/jobs/{job_id}", timeout=10)
    print(f"GET /api/v1/jobs/{job_id} ->", r.status_code)
    pprint(r.json())

def get_resume(resume_id):
    r = requests.get(f"{BASE}/api/v1/resumes/{resume_id}", timeout=10)
    print(f"GET /api/v1/resumes/{resume_id} ->", r.status_code)
    pprint(r.json())

def main():
    try:
        job = post_job()
        resume = post_resume()

        # Depending on your API, returned id might be in field "id" or "_id"
        job_id = job.get("id") or job.get("_id") or job.get("_key")  # try a few
        resume_id = resume.get("id") or resume.get("_id") or resume.get("_key")

        if job_id:
            get_job(job_id)
        else:
            print("Could not determine job id from response:", job)

        if resume_id:
            get_resume(resume_id)
        else:
            print("Could not determine resume id from response:", resume)

    except Exception as e:
        print("Error during smoke test:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
