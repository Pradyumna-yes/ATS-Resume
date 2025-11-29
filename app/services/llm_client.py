import hashlib, json
from app.core.config import settings
import httpx

def _cache_key(stage: str, payload: dict):
    key_input = json.dumps({"stage":stage,"payload":payload,"seed":settings.DETERMINISTIC_SEED}, sort_keys=True)
    return hashlib.sha256(key_input.encode()).hexdigest()

def run_stage(stage_name: str, payload: dict, config: dict):
    key = _cache_key(stage_name, payload)
    # check redis/db cache here...
    # if cached, return cached result
    # otherwise call LLM provider
    system_prompt = load_system_prompt_for_stage(stage_name)
    # call to the LLM provider (DeepSeek), synchronous or via HTTP SDK
    response_json = call_llm_api(system_prompt, payload, config)
    # validate JSON schema (use pydantic) - ensure strict schema match
    # store in cache
    return response_json
