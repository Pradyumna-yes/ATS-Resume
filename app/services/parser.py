# app/services/parser.py
from typing import Dict, List, Any
import re

def parse_resume_text(text: str) -> Dict[str, Any]:
    """
    Minimal rule-based parser to produce a basic resume JSON structure.
    This is a fallback; replace with your robust parser for production.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    joined = "\n".join(lines)

    # guess contact block (first 5 lines)
    contact_guess = lines[:5]

    # skills block: look for "Skills", "Technical Skills", etc.
    skills = []
    m = re.search(r"(?:Skills|Technical Skills|Skills:)([\s\S]{0,400})", joined, re.IGNORECASE)
    if m:
        s = m.group(1).strip()
        # rudimentary split on commas or newlines
        skills = [x.strip() for x in re.split(r"[\n,;]", s) if x.strip()][:50]

    # experience heuristics: look for years or "•" bullets
    bullets = re.findall(r"[-•\u2022]\s*(.+)", joined)
    if not bullets:
        # fallback: break by sentences
        bullets = re.split(r"\.\s+", joined)[:20]

    parsed = {
        "contact": {"raw": "\n".join(contact_guess)},
        "skills": skills,
        "experience_bullets": bullets[:20],
        "raw_text": joined,
        "confidence": 0.6,
    }
    return parsed

def parse_job_text(text: str) -> Dict[str, Any]:
    """
    Lightweight JD parser: extract title, locations, required lists.
    """
    joined = text.strip()
    # role title heuristic: first line up to 100 chars
    first_line = joined.splitlines()[0] if joined.splitlines() else ""
    title = first_line.strip()[:100]

    # required/preferred lists -- look for keywords
    must = []
    nice = []
    # find enumerated lines under headings
    required_match = re.search(r"(?:Required Qualifications|Required|Qualifications:)([\s\S]{0,400})", joined, re.IGNORECASE)
    if required_match:
        must = [l.strip("-•* \t") for l in re.split(r"[\n\r]+", required_match.group(1)) if l.strip()][:30]
    preferred_match = re.search(r"(?:Preferred Qualifications|Preferred|Nice to have:)([\s\S]{0,400})", joined, re.IGNORECASE)
    if preferred_match:
        nice = [l.strip("-•* \t") for l in re.split(r"[\n\r]+", preferred_match.group(1)) if l.strip()][:30]

    return {
        "role_title": title,
        "must_have_skills": must,
        "nice_to_have_skills": nice,
        "raw_text": joined,
        "confidence": 0.65,
    }
