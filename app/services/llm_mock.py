# app/services/llm_mock.py
"""
Deterministic mock LLM runner.

Given a stage name and input JSON, return a deterministic JSON response.
This uses a simple hashing + seed so repeated runs produce the same outputs.
"""
from typing import Dict, Any
import hashlib
import json

def _hash_to_float(s: str) -> float:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    # take first 8 hex digits to int, normalize [0,1)
    v = int(h[:8], 16) / float(0xFFFFFFFF)
    return v

def run_stage(stage: str, input_json: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    """
    stage: e.g., "JD_NORMALIZER", "JD_EXTRACT", "RESUME_PARSE", etc.
    Returns a deterministic JSON payload consistent across calls for same input + seed.
    """
    # canonicalize input
    s = json.dumps({"stage": stage, "seed": seed, "input": input_json}, sort_keys=True, ensure_ascii=False)
    base = _hash_to_float(s)

    # Simple deterministic outputs per stage — real LLM will replace this
    if stage == "A_JD_NORMALIZER":
        return {
            "cleaned_text": input_json.get("content", "")[:2000],
            "company": input_json.get("company", "unknown"),
            "role_title": input_json.get("title", "Unknown Role"),
            "posting_date": input_json.get("posted_date", None),
            "ats_candidates": [{"name": "GenericATS", "confidence": round(base, 2)}],
            "notes": "mocked normalizer",
            "confidence": round(0.5 + base * 0.5, 3)
        }
    if stage == "B_JD_EXTRACT":
        # simple token extraction: split by commas/words
        text = input_json.get("cleaned_text", "") or input_json.get("content", "")
        tokens = list({w.strip().strip(".,()") for w in text.split() if len(w) > 2})[:20]
        must = tokens[:3]
        nice = tokens[3:6]
        ats_terms = [{"term": t, "platform_relevance": {"GenericATS": round(0.8*base,2)}} for t in tokens[:10]]
        return {
            "role_title": input_json.get("role_title", "Unknown"),
            "seniority": "Mid-level" if base > 0.5 else "Entry",
            "years_experience": {"min": 2, "max": 5},
            "must_have_skills": must,
            "nice_to_have_skills": nice,
            "non_negotiable": [],
            "tools": tokens[6:9],
            "certifications": [],
            "ats_keyword_list": ats_terms,
            "skill_categories": {"technical": must + nice},
            "confidence": round(0.6 + base * 0.4, 3)
        }
    if stage == "C_RESUME_PARSE":
        # simple parse: pretend resume_text is passed
        text = input_json.get("file_text", "")[:2000]
        skills = ["SQL", "Python"] if "SQL" in text or "Python" in text else ["Communication"]
        return {
            "contact": {"name": "Test User", "email": "test@example.com"},
            "skills": skills,
            "experience": [{"company": "ACME", "title": "Analyst", "start":"2019-01", "end":"2022-01", "bullets":[text[:120]]}],
            "education": [],
            "suspicious_claims": [],
            "original_layout": input_json.get("original_layout", {}),
            "confidence": round(0.6 + base * 0.4, 3)
        }
    if stage == "D_MATCHER_SCORER":
        # simplistic scoring: fraction of must-have skills present
        jd_skills = set(input_json.get("jd", {}).get("must_have_skills", []))
        resume_skills = set(input_json.get("resume", {}).get("skills", []))
        if not jd_skills:
            skills_pct = 0.0
        else:
            skills_pct = len(jd_skills & resume_skills) / len(jd_skills)
        score = round(50 + skills_pct * 50 * base, 2)
        return {
            "matching_summary": {"must_have_match_pct": round(skills_pct * 100,2)},
            "score": score,
            "score_breakdown": {"skills": round(skills_pct*40,2), "ats_keywords": round(20*base,2), "format": 10, "parseability": 10},
            "matches": [{"term": s, "found": s in resume_skills, "match_type": "exact"} for s in list(jd_skills)][:10],
            "misses": [{"term": t, "reason":"not found"} for t in jd_skills - resume_skills],
            "confidence": round(0.6 + base*0.3,3)
        }
    if stage == "E_RECOMMEND":
        # produce a small list of recommendations
        recs = []
        must = input_json.get("jd", {}).get("must_have_skills", [])[:3]
        for idx,s in enumerate(must):
            recs.append({"level":"High","action":f"Add '{s}' to Skills section","impact":5})
        return {"recommendation_list": recs, "latex_actions": [], "confidence": round(0.6+base*0.4,3)}
    if stage == "F_LATEX_ADAPT":
        return {"patches": [{"file":"resume.tex","insert":"% example inserted"}], "preview_info":{"pages":1}, "confidence": round(0.5+base*0.4,3)}
    # default fallback
    return {"note":"unhandled stage","confidence": round(base,3)}
