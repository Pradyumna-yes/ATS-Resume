# tests/test_resume_parser.py
import pytest
from app.services.resume_parser import parse_resume_text

SAMPLE_TEXT = """
JOHN DOE
john.doe@example.com | +1 555-123-4567 | Dublin, Ireland

Professional Summary
Experienced Data Analyst with 5+ years working on BI solutions.

Skills
SQL, Power BI, Python, Tableau

Professional Experience
Senior Data Analyst — Acme Inc.
2019-06 - 2023-02
- Built Power BI dashboards used by 200+ users, reducing reporting time by 30%.
- Developed ETL pipelines and data models.

Data Analyst — Beta Corp
2016 - 2019
- Wrote SQL queries and improved ETL processes.

Education
BSc in Computer Science, University of Somewhere, 2013-2016
"""

def test_basic_parse():
    parsed = parse_resume_text(SAMPLE_TEXT)
    assert parsed["contact"]["email"] == "john.doe@example.com"
    assert "Power BI" in parsed["skills"]
    assert len(parsed["experience"]) >= 2
    # check metrics extraction in first experience
    first = parsed["experience"][0]
    assert any(m['type'] == 'percent' for m in first['metrics'])
    assert parsed["confidence"] > 0

def test_suspicious_overlap():
    text = """
    Experience
    Role A — CoA
    2018 - 2020
    - Worked on projects

    Role B — CoB
    2019 - 2021
    - Overlapping role
    """
    parsed = parse_resume_text(text)
    suspicious = parsed["suspicious_claims"]
    assert any("Overlapping" in s["text"] for s in suspicious)
