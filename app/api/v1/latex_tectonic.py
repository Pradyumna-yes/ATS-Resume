# app/api/v1/latex_tectonic.py
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Optional
import asyncio
from app.api.v1.auth import get_current_user
from app.services.latex_tectonic_runner import compile_tex_with_tectonic
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

class TectonicCompileRequest(BaseModel):
    tex_source: Optional[str] = None
    template_name: Optional[str] = None
    patches: Optional[dict] = None
    timeout_sec: Optional[int] = None

@router.post("/latex/compile-tectonic")
async def compile_tectonic_endpoint(req: TectonicCompileRequest = Body(...), current_user=Depends(get_current_user)):
    """
    Compile LaTeX using Tectonic in short-lived container (on-demand).
    Accepts either tex_source OR template_name + patches.
    Returns application/pdf streaming response on success.
    """
    if not req.tex_source and not req.template_name:
        raise HTTPException(status_code=400, detail="Provide tex_source or template_name")

    # load template if requested
    tex = req.tex_source
    if not tex and req.template_name:
        from app.services.latex_compiler import TEMPLATES_DIR  # reuse templates dir
        template_path = TEMPLATES_DIR / req.template_name
        if not template_path.exists():
            raise HTTPException(status_code=404, detail="Template not found")
        tex = template_path.read_text(encoding="utf-8")
        if req.patches:
            for k, v in req.patches.items():
                tex = tex.replace(f"{{{{{k}}}}}", str(v))

    timeout = req.timeout_sec or None

    loop = asyncio.get_event_loop()
    # run the blocking compile in a threadpool (calls docker)
    success, pdf_bytes, log = await loop.run_in_executor(None, compile_tex_with_tectonic, tex, None, timeout)

    if not success:
        raise HTTPException(status_code=500, detail={"compiled": False, "log": log})

    # stream pdf bytes back
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf")
