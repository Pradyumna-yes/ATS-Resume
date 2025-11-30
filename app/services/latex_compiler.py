# app/services/latex_compiler.py
import tempfile
import pathlib
import shutil
import subprocess
import os
from typing import Tuple, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

# Where to look for template files (package relative)
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates" / "latex"

# Default timeout for compilation (seconds)
DEFAULT_TIMEOUT = int(os.getenv("LATEX_COMPILE_TIMEOUT", "20"))
# Max PDF size to return (bytes)
MAX_PDF_BYTES = int(os.getenv("LATEX_MAX_PDF_BYTES", str(10 * 1024 * 1024)))  # 10MB

def _sanitize_filename(name: str) -> str:
    # Basic sanitize: allow alnum, underscore, dash, dot
    return "".join([c for c in name if c.isalnum() or c in ("_", "-", ".")]).strip() or "resume"

def compile_latex(tex_source: str, workdir_root: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, bytes, str]:
    """
    Compiles tex_source to PDF using latexmk (fallback to pdflatex).
    Returns (success, pdf_bytes_or_empty, log_text).
    This function is blocking and should be run in a worker thread if called from async code.
    """
    work_root = pathlib.Path(workdir_root) if workdir_root else None
    tmpdir = tempfile.mkdtemp(prefix="latex_compile_", dir=str(work_root) if work_root else None)
    tmpdir_path = pathlib.Path(tmpdir)
    try:
        main_tex_name = f"{_sanitize_filename('resume')}.tex"
        tex_path = tmpdir_path / main_tex_name
        tex_path.write_text(tex_source, encoding="utf-8")

        # run latexmk if available, else fallback to pdflatex twice
        # latexmk flags: -pdf (produce pdf), -interaction=nonstopmode, -halt-on-error
        # Do not enable -shell-escape to avoid executing shell commands.
        # prefer discovered binaries, but if which() returns None still try the binary name
        latexmk_cmd = shutil.which("latexmk") or "latexmk"
        pdflatex = shutil.which("pdflatex") or "pdflatex"
        # try latexmk first
        cmd = [latexmk_cmd, "-pdf", "-interaction=nonstopmode", "-halt-on-error", main_tex_name]

        logger.info("Starting LaTeX compile: %s", cmd)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(tmpdir_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            log = proc.stdout.decode("utf-8", errors="replace")
            final_returncode = proc.returncode
            # if latexmk was not available or returned non-zero, try pdflatex fallback
            if final_returncode != 0 and pdflatex:
                proc2 = subprocess.run(
                    [pdflatex, "-interaction=nonstopmode", "-halt-on-error", main_tex_name],
                    cwd=str(tmpdir_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
                log += "\n\nPDFFALLBACK OUTPUT:\n" + proc2.stdout.decode("utf-8", errors="replace")
                final_returncode = proc2.returncode
        except subprocess.TimeoutExpired as te:
            logger.exception("LaTeX compile timed out")
            return False, b"", f"Timeout after {timeout}s\n{str(te)}"
        except FileNotFoundError:
            # binary not found - treat as unavailable
            logger.error("LaTeX binary not found: latexmk/pdflatex")
            return False, b"", "Error: latexmk/pdflatex not available in runtime"

        pdf_path = tmpdir_path / (main_tex_name.replace(".tex", ".pdf"))
        try:
            pdf_bytes = pdf_path.read_bytes()
        except FileNotFoundError:
            logger.warning("LaTeX compile failed (returncode=%s) - PDF missing", final_returncode)
            return False, b"", log
        if len(pdf_bytes) > MAX_PDF_BYTES:
            logger.warning("Compiled PDF exceeds max size (%s bytes)", len(pdf_bytes))
            # do not return huge files
            return False, b"", log + f"\n\nCompiled PDF too large: {len(pdf_bytes)} bytes"

        return True, pdf_bytes, log

    except subprocess.TimeoutExpired as te:
        logger.exception("LaTeX compile timed out")
        return False, b"", f"Timeout after {timeout}s\n{str(te)}"
    except Exception as exc:
        logger.exception("Unexpected error during LaTeX compile")
        return False, b"", f"Error: {str(exc)}"
    finally:
        # cleanup
        try:
            shutil.rmtree(tmpdir_path)
        except Exception:
            pass
