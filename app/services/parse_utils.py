# app/services/parse_utils.py
"""
Helpers to extract text from common resume file bytes.
- PDF -> uses pdfminer.six
- DOCX -> uses python-docx
- TXT  -> decode bytes
"""

from typing import Tuple
import io

def _is_pdf_bytes(b: bytes) -> bool:
    return b.startswith(b"%PDF")

def _is_docx_bytes(b: bytes) -> bool:
    # docx is a zip archive with '[Content_Types].xml' file; check PK header
    return b.startswith(b"PK")

def parse_text_bytes(b: bytes, encoding: str = "utf-8") -> str:
    try:
        return b.decode(encoding, errors="replace")
    except Exception:
        return b.decode("utf-8", errors="replace")

def parse_docx_bytes(b: bytes) -> str:
    try:
        from docx import Document
    except Exception as e:
        raise RuntimeError("python-docx not installed") from e

    stream = io.BytesIO(b)
    doc = Document(stream)
    paras = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paras)

def parse_pdf_bytes(b: bytes) -> str:
    """
    Extract text from PDF bytes using pdfminer.six high-level API.
    """
    try:
        from pdfminer.high_level import extract_text_to_fp
    except Exception as e:
        raise RuntimeError("pdfminer.six not installed") from e

    output = io.StringIO()
    stream = io.BytesIO(b)
    # leave codec/params as defaults
    extract_text_to_fp(stream, output, laparams=None)
    return output.getvalue()

def extract_text_auto(b: bytes) -> Tuple[str, str]:
    """
    Try to detect type and parse. Returns (text, type_str).
    type_str one of: "pdf","docx","txt","unknown"
    """
    if not b:
        return "", "unknown"

    if _is_pdf_bytes(b):
        try:
            return parse_pdf_bytes(b), "pdf"
        except Exception:
            # fallback to text decode
            return parse_text_bytes(b), "pdf_fallback"
    if _is_docx_bytes(b):
        try:
            return parse_docx_bytes(b), "docx"
        except Exception:
            # fallback
            return parse_text_bytes(b), "docx_fallback"

    # default attempt decode as text
    return parse_text_bytes(b), "txt"
