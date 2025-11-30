# tests/test_latex_compiler.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.latex_compiler import compile_latex

SIMPLE_TEX = r"""
\documentclass{article}
\begin{document}
Hello World
\end{document}
"""

@pytest.mark.parametrize("latexmk_available", [True, False])
def test_compile_success(monkeypatch, latexmk_available):
    # Mock shutil.which to simulate presence/absence of latexmk/pdflatex
    import shutil
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/latexmk" if latexmk_available and name == "latexmk" else ("/usr/bin/pdflatex" if name == "pdflatex" else None))

    # Patch subprocess.run to simulate successful compilation and PDF file creation
    class FakeProc:
        def __init__(self):
            self.returncode = 0
            self.stdout = b"OK"

    def fake_run(cmd, cwd, stdout, stderr, timeout, check):
        return FakeProc()

    monkeypatch.setattr("subprocess.run", fake_run)

    # Also mock pdf file creation by creating file in a temp dir inside compile_latex (we cannot easily capture tmpdir here)
    # Instead, monkeypatch pathlib.Path.read_bytes to return sample bytes when reading .pdf path
    import pathlib
    real_read_bytes = pathlib.Path.read_bytes
    def fake_read_bytes(self):
        if str(self).endswith(".pdf"):
            return b"%PDF-1.4 fakepdf"
        return real_read_bytes(self)
    monkeypatch.setattr("pathlib.Path.read_bytes", fake_read_bytes)

    success, pdf_bytes, log = compile_latex(SIMPLE_TEX, timeout=5)
    assert success
    assert pdf_bytes.startswith(b"%PDF")
    assert "OK" in log or isinstance(log, str)

def test_compile_timeout(monkeypatch):
    # Simulate subprocess timeout
    import subprocess
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="latexmk", timeout=1)
    monkeypatch.setattr("subprocess.run", fake_run)
    success, pdf, log = compile_latex(SIMPLE_TEX, timeout=1)
    assert not success
    assert "Timeout" in log
