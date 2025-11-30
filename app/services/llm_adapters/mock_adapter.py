import asyncio

async def run_stage(stage_name: str, payload: dict, seed: int = 42) -> dict:
    # deterministic mock that returns simple structure
    await asyncio.sleep(0)  # yield
    return {
        "stage": stage_name,
        "confidence": 0.9,
        "skills": payload.get("file_text", "").split(),
    }
