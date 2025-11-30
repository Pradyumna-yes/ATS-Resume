# app/services/pipeline.py
"""
Master orchestration for the ATS Resume Analyzer pipeline.

Stages:
  A_JD_NORMALIZER
  B_JD_EXTRACT
  C_RESUME_PARSE
  D_MATCHER_SCORER
  E_RECOMMEND
  F_LATEX_ADAPT

Behavior:
- Uses pluggable LLM adapter via app.services.llm_adapter.run_stage
- Uses deterministic parser when resume.file_text is present for Stage C
- Uses deterministic cache (app.services.deterministic_cache.cache) to avoid re-running stages
- Persists final assessment using app.repositories.assessments.create_assessment
- Returns final structured assessment JSON
"""

import json
import hashlib
import uuid
from typing import Any, Dict, Tuple
from datetime import datetime
import asyncio
import logging

from app.services.llm_adapter import run_stage
from app.services.resume_parser import parse_resume_text
from app.services.deterministic_cache import cache
from app.repositories.assessments import create_assessment
from app.models.assessment import AssessmentCreate

logger = logging.getLogger(__name__)

# Define the canonical ordered stages
STAGES = [
    ("A_JD_NORMALIZER", "JD Normalizer & ATS Detector"),
    ("B_JD_EXTRACT", "JD Extractor"),
    ("C_RESUME_PARSE", "Resume Parser"),
    ("D_MATCHER_SCORER", "Matcher & Scorer"),
    ("E_RECOMMEND", "Recommendation Generator"),
    ("F_LATEX_ADAPT", "LaTeX Suggest Adapter"),
]

def _serialize_for_cache(obj: Any) -> str:
    """
    Deterministic JSON serialization used for cache keys.
    """
    try:
        return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        # fallback to repr if something non-jsonable sneaks in
        return repr(obj)

def _cache_key(stage_name: str, payload: Dict[str, Any], seed: int) -> str:
    """
    Create a stable cache key for a stage using SHA256 of serialized payload+seed.
    """
    s = f"{stage_name}|{seed}|{_serialize_for_cache(payload)}"
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return f"pipeline:{stage_name}:{h}"

async def _run_stage_with_cache(stage_name: str, payload: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """
    Run a stage with cache lookup. Uses async `cache.get` and `cache.set`.
    """
    key = _cache_key(stage_name, payload, seed)
    try:
        cached = await cache.get(key)
        if cached is not None:
            # cached expected to be JSON-serializable; ensure dict
            if isinstance(cached, str):
                try:
                    return json.loads(cached)
                except Exception:
                    return cached
            return cached
    except Exception as exc:
        # don't fail the pipeline for cache errors
        logger.debug("Cache get error for key %s: %s", key, exc)

    # run the stage via LLM adapter
    try:
        result = await run_stage(stage_name, payload, seed=seed)
    except Exception as exc:
        # return a structured error object for the stage
        logger.exception("Error running stage %s: %s", stage_name, exc)
        result = {"error": True, "error_message": str(exc), "confidence": 0.0}

    # try to set cache (best-effort)
    try:
        # ensure cache stores JSON-serializable content (string)
        await cache.set(key, result)
    except Exception as exc:
        logger.debug("Cache set error for key %s: %s", key, exc)

    return result

async def run_assessment_pipeline(job_payload: Dict[str, Any], resume_payload: Dict[str, Any], seed: int = 42) -> Dict[str, Any]:
    """
    Run the full pipeline for a given job and resume payload.

    Inputs:
      job_payload: {"raw_text": "...", "source_url": "...", "company": "...", "job_id": "...", ...}
      resume_payload: {"file_text":"...", "file_format":"pdf", "resume_id":"...", "original_layout": {...}, ...}
      seed: deterministic seed to keep results stable

    Returns:
      final assessment JSON including stages and assessment_id when persisted.
    """
    results: Dict[str, Any] = {}

    # Iterate through stages in order
    for (stage_name, stage_desc) in STAGES:
        try:
            # Build stage-specific input payloads
            if stage_name == "A_JD_NORMALIZER":
                payload = {
                    "content": job_payload.get("raw_text", "") or job_payload.get("content", ""),
                    "source_url": job_payload.get("source_url"),
                    "company": job_payload.get("company"),
                    "config": job_payload.get("config", {"infer_ats": True})
                }
                out = await _run_stage_with_cache(stage_name, payload, seed)
            elif stage_name == "B_JD_EXTRACT":
                prev_a = results.get("A_JD_NORMALIZER", {})
                payload = {
                    "cleaned_text": prev_a.get("cleaned_text", job_payload.get("raw_text", "")),
                    "ats_candidates": prev_a.get("ats_candidates", []),
                    "config": {"platform": prev_a.get("ats_candidates", [{}])[0].get("name") if prev_a.get("ats_candidates") else None, "prioritize_ats_keywords": True}
                }
                out = await _run_stage_with_cache(stage_name, payload, seed)
            elif stage_name == "C_RESUME_PARSE":
                # If resume_payload has raw extracted text, use deterministic parser
                file_text = resume_payload.get("file_text")
                if file_text:
                    # parse synchronously (but run via run_in_executor to avoid blocking event loop heavy work)
                    loop = asyncio.get_event_loop()
                    parsed = await loop.run_in_executor(None, parse_resume_text, file_text, resume_payload.get("original_layout", {}))
                    # ensure we provide a confidence field
                    if "confidence" not in parsed:
                        parsed["confidence"] = parsed.get("confidence", 0.8)
                    out = parsed
                    # store to cache as well
                    try:
                        key = _cache_key(stage_name, {"file_text": file_text, "original_layout": resume_payload.get("original_layout", {})}, seed)
                        await cache.set(key, out)
                    except Exception:
                        pass
                else:
                    payload = {"file_text": "", "original_layout": resume_payload.get("original_layout", {})}
                    out = await _run_stage_with_cache(stage_name, payload, seed)
            elif stage_name == "D_MATCHER_SCORER":
                payload = {"jd": results.get("B_JD_EXTRACT", {}), "resume": results.get("C_RESUME_PARSE", {}), "config": job_payload.get("scoring_config", {})}
                out = await _run_stage_with_cache(stage_name, payload, seed)
            elif stage_name == "E_RECOMMEND":
                payload = {"score": results.get("D_MATCHER_SCORER", {}).get("score"), "jd": results.get("B_JD_EXTRACT", {}), "resume": results.get("C_RESUME_PARSE", {}), "config": job_payload.get("recommend_config", {})}
                out = await _run_stage_with_cache(stage_name, payload, seed)
            elif stage_name == "F_LATEX_ADAPT":
                payload = {"recommendation": results.get("E_RECOMMEND", {}), "template": job_payload.get("template", "onepage")}
                out = await _run_stage_with_cache(stage_name, payload, seed)
            else:
                # generic fallback
                out = await _run_stage_with_cache(stage_name, {}, seed)
        except Exception as exc:
            logger.exception("Unhandled error in pipeline stage %s: %s", stage_name, exc)
            out = {"error": True, "error_message": str(exc), "confidence": 0.0}

        # store stage output
        results[stage_name] = out

    # Build final assessment object
    final_score = results.get("D_MATCHER_SCORER", {}).get("score", 0)
    final = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "stages": results,
        "final_score": final_score,
        "job_id": job_payload.get("job_id"),
        "resume_id": resume_payload.get("resume_id"),
        "meta": {
            "seed": seed,
            "job_source": job_payload.get("source_url"),
            "company": job_payload.get("company"),
            "role_title": results.get("B_JD_EXTRACT", {}).get("role_title")
        }
    }

    # Persist assessment (best-effort). Build AssessmentCreate model for repository
    try:
        ac = AssessmentCreate(
            user_id=job_payload.get("user_id") or resume_payload.get("user_id"),
            job_id=job_payload.get("job_id"),
            resume_id=resume_payload.get("resume_id"),
            final_score=float(final_score) if final_score is not None else 0.0,
            results=final,
            metadata={"persisted_at": datetime.utcnow().isoformat()}
        )
        saved_id = await create_assessment(ac)
        final["assessment_id"] = saved_id
    except Exception as exc:
        logger.exception("Failed to persist assessment: %s", exc)
        final["assessment_id"] = None

    return final
