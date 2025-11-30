# app/api/v1/latex.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import asyncio
from app.services.latex_compiler import compile_latex
from app.api.v1.auth import get_current_user  # optional auth
import base64
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class CompileRequest(BaseModel):
    tex_source: Optional[str] = None
    template_name: Optional[str] = None  # e.g., "onepage.tex"
    patches: Optional[dict] = None  # simple key->value patches to insert
    timeout_sec: Optional[int] = None

@router.post("/latex/compile")
async def compile_endpoint(req: CompileRequest, current_user = Depends(get_current_user)):
    """
    Compile LaTeX source or template+patches to PDF.
    Request body: {tex_source | template_name + patches}
    Returns: {success:bool, log:str, pdf_base64: str|None}
    """
    if not req.tex_source and not req.template_name:
        raise HTTPException(status_code=400, detail="Either tex_source or template_name required")

    # Build tex source: either direct or from template + patches
    if req.tex_source:
        tex = req.tex_source
    else:
        # load template file
        from pathlib import Path
        from app.services.latex_compiler import TEMPLATES_DIR
        template_path = TEMPLATES_DIR / req.template_name
        if not template_path.exists():
            raise HTTPException(status_code=400, detail="Template not found")
        tex = template_path.read_text(encoding="utf-8")
        # apply simple patches replacing {{key}} placeholders
        if req.patches:
            for k, v in (req.patches.items()):
                tex = tex.replace(f"{{{{{k}}}}}", str(v))

    # Run compile in threadpool
    loop = asyncio.get_event_loop()
    timeout = req.timeout_sec or None
    success, pdf_bytes, log = await loop.run_in_executor(None, compile_latex, tex, None, timeout or None)

    if not success:
        raise HTTPException(status_code=500, detail={"compiled": False, "log": log})

    # base64 encode pdf to return JSON safely (or stream directly)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return {"compiled": True, "log": log, "pdf_base64": pdf_b64}
