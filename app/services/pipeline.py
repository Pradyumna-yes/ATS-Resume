# app/services/pipeline.py (only updated run_assessment_pipeline function)
from typing import Dict, Any
import asyncio
from app.services.llm_adapter import run_stage
from app.services.deterministic_cache import cache
from app.db.documents import Assessment, JobPosting, Resume
from datetime import datetime
import uuid
from app.utils.deterministic_cache import make_cache_key

# new import
from app.services.resume_parser import parse_resume_text

async def run_assessment_pipeline(job_payload: Dict[str,Any], resume_payload: Dict[str,Any], seed: int = 42) -> Dict[str,Any]:
    results = {}
    # Define the ordered pipeline stages (name, metadata)
    STAGES = [
        ("A_JD_NORMALIZER", {}),
        ("B_JD_EXTRACT", {}),
        ("C_RESUME_PARSE", {}),
        ("D_MATCHER_SCORER", {}),
        ("E_RECOMMEND", {}),
        ("F_LATEX_ADAPT", {}),
    ]
    for stage_name, _ in STAGES:
        key = make_cache_key(stage_name, {"job": job_payload, "resume": resume_payload}, seed)
        cached = None
        try:
            cached = await cache.get(key)
        except Exception:
            cached = None
        if cached is not None:
            results[stage_name] = cached
            continue

        # build stage-specific input
        stage_input = {}
        if stage_name == "A_JD_NORMALIZER":
            stage_input = {"content": job_payload.get("raw_text",""), "company": job_payload.get("company")}
            out = await run_stage(stage_name, stage_input, seed=seed)
        elif stage_name == "B_JD_EXTRACT":
            stage_input = {"cleaned_text": results.get("A_JD_NORMALIZER", {}).get("cleaned_text", ""), "role_title": results.get("A_JD_NORMALIZER",{}).get("role_title")}
            out = await run_stage(stage_name, stage_input, seed=seed)
        elif stage_name == "C_RESUME_PARSE":
            # If we already have file_text from resume_payload, use deterministic rule-based parser
            if resume_payload.get("file_text"):
                parsed = parse_resume_text(resume_payload.get("file_text", ""), original_layout=resume_payload.get("original_layout", {}))
                out = parsed
                out["confidence"] = out.get("confidence", 0.8)
            else:
                # fallback to LLM-based mock parser
                stage_input = {"file_text": resume_payload.get("file_text",""), "original_layout": resume_payload.get("original_layout", {})}
                out = await run_stage(stage_name, stage_input, seed=seed)
        elif stage_name == "D_MATCHER_SCORER":
            stage_input = {"jd": results.get("B_JD_EXTRACT", {}), "resume": results.get("C_RESUME_PARSE", {})}
            out = await run_stage(stage_name, stage_input, seed=seed)
        elif stage_name == "E_RECOMMEND":
            stage_input = {"score": results.get("D_MATCHER_SCORER", {}).get("score"), "jd": results.get("B_JD_EXTRACT", {}), "resume": results.get("C_RESUME_PARSE", {})}
            out = await run_stage(stage_name, stage_input, seed=seed)
        elif stage_name == "F_LATEX_ADAPT":
            stage_input = {"recommendation": results.get("E_RECOMMEND", {}), "template":"onepage"}
            out = run_stage(stage_name, stage_input, seed=seed)
        else:
            out = await run_stage(stage_name, {}, seed=seed)

        results[stage_name] = out
        # store to cache
        try:
            await cache.set(key, out)
        except Exception:
            pass

    final = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "stages": results,
        "final_score": results.get("D_MATCHER_SCORER", {}).get("score", 0)
    }
    try:
        a = Assessment(score=final["final_score"], results_json=final)
        await a.insert()
        final["assessment_id"] = str(a.id)
    except Exception:
        final["assessment_id"] = None
    return final
