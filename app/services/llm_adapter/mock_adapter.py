# app/services/llm_adapters.mock_adapter.py
"""
Deterministic mock adapter to mimic LLM stages for testing and CI.
This is async-compatible and deterministic based on stage_name + seed.
"""

import asyncio
import hashlib
import json
from typing import Dict, Any

# A small deterministic generator for stage outputs
async def run_stage(stage_name: str, payload: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    await asyncio.sleep(0)  # keep async signature
    # deterministic hash to vary content by stage + seed
    h = hashlib.sha256(f"{stage_name}:{seed}".encode()).hexdigest()[:8]
    # Return shape differs by stage_name minimally
    if stage_name == "A_JD_NORMALIZER":
        return {
            "cleaned_text": payload.get("content",""),
            "company": payload.get("company",""),
            "role_title": payload.get("role_title",""),
            "confidence": 0.9
        }
    if stage_name == "B_JD_EXTRACT":
        return {
            "role_title": "Data Analyst",
            "seniority": "Mid-level",
            "must_have_skills": ["SQL","Power BI","data modeling"],
            "nice_to_have_skills": ["Python","ETL"],
            "ats_keyword_list": [{"term":"Power BI","platform_relevance":{"Workday":0.9}}],
            "confidence": 0.95
        }
    if stage_name == "C_RESUME_PARSE":
        return {
            "contact": {"name": "Jane Doe", "email": "jane@example.com"},
            "skills": ["SQL","Power BI"],
            "experience": [],
            "confidence": 0.8
        }
    if stage_name == "D_MATCHER_SCORER":
        return {"matching_summary": {"must_have_match_pct": 0.67}, "score": 76.4}
    if stage_name == "E_RECOMMEND":
        return {"recommendation_list": [{"level":"High","text":"Add Power BI"}]}
    if stage_name == "F_LATEX_ADAPT":
        return {"latex_snippet": "\\\\skill{Power BI}"}
    # default fallback
    return {"stage": stage_name, "seed": seed, "hash": h}
