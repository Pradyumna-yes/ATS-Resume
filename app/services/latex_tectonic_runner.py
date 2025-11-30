# app/services/latex_tectonic_runner.py
"""
Tectonic runner that compiles a .tex source by launching a short-lived Docker container.
This keeps the LaTeX runtime isolated in the container and avoids installing TeX on the host.

API:
- compile_tex_with_tectonic(tex_source: str, timeout: int = 30, image: str = "latex-tectonic:latest") -> (success: bool, pdf_bytes: bytes, log: str)

Implementation details:
- creates a temporary directory
- writes resume.tex
- runs `docker run --rm -v <tempdir>:/data latex-tectonic tectonic /data/resume.tex --outdir /data`
- reads /data/resume.pdf and returns bytes
- cleans up tempdir
"""

import tempfile
import pathlib
import subprocess
import shutil
import os
import uuid
from typing import Tuple, Optional

DEFAULT_IMAGE = os.getenv("TEX_IMAGE", "latex-tectonic:latest")
DEFAULT_TIMEOUT = int(os.getenv("TEX_DOCKER_TIMEOUT", "30"))  # seconds

def _sanitize_name(n: str) -> str:
    return "".join(c for c in n if c.isalnum() or c in ("-", "_", ".")).strip() or "resume"

def compile_tex_with_tectonic(
    tex_source: str,
    image: str = DEFAULT_IMAGE,
    timeout: int = DEFAULT_TIMEOUT,
    workdir_root: Optional[str] = None,
) -> Tuple[bool, bytes, str]:
    """
    Blocking call. Returns (success, pdf_bytes_or_empty, log_text).
    Raises no exceptions - always returns (False, b'', log) on error.
    """
    tmp_root = pathlib.Path(workdir_root) if workdir_root else None
    tmpdir = tempfile.mkdtemp(prefix="tectonic_", dir=str(tmp_root) if tmp_root else None)
    tmpdir_path = pathlib.Path(tmpdir)
    try:
        texname = _sanitize_name("resume") + ".tex"
        tex_path = tmpdir_path / texname
        tex_path.write_text(tex_source, encoding="utf-8")

        # Build docker run command
        # Mount tmpdir as /data and run tectonic on the file, placing output in /data
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network", "none",  # remove network for extra safety
            "-v", f"{str(tmpdir_path)}:/data:Z",
            image,
            "tectonic",
            f"/data/{texname}",
            "--outdir", "/data"
        ]

        # run the docker command
        proc = subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        out = proc.stdout.decode("utf-8", errors="replace")

        # expected PDF path
        pdf_path = tmpdir_path / texname.replace(".tex", ".pdf")
        if proc.returncode != 0 or not pdf_path.exists():
            return False, b"", out

        pdf_bytes = pdf_path.read_bytes()
        return True, pdf_bytes, out

    except subprocess.TimeoutExpired as te:
        return False, b"", f"Timeout after {timeout}s: {str(te)}"
    except FileNotFoundError as fe:
        # docker binary not found or image missing
        return False, b"", f"Runtime error: {str(fe)}"
    except Exception as exc:
        return False, b"", f"Error: {str(exc)}"
    finally:
        # best-effort cleanup
        try:
            shutil.rmtree(tmpdir_path)
        except Exception:
            pass
