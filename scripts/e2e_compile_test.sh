#!/usr/bin/env bash
set -euo pipefail

# config
API_URL=${API_URL:-http://127.0.0.1:8000}
IMAGE_NAME=${IMAGE_NAME:-latex-tectonic:latest}
TEX_FILE=${TEX_FILE:-sample_resume.tex}
OUT_PDF=${OUT_PDF:-out_resume.pdf}
JWT_TOKEN=${JWT_TOKEN:-}  # if you have a JWT locally, set it: export JWT_TOKEN="eyJ..."

# 1) build tectonic image (skip if already built)
echo "Building tectonic image (if not already built)..."
docker build -f Dockerfile.compile.tectonic -t ${IMAGE_NAME} .

# 2) start uvicorn in background if not running
# Assumes your FastAPI app runs with `uvicorn app.main:app --reload`
# If you already have the server running, skip this.
if ! nc -z 127.0.0.1 8000; then
  echo "Starting uvicorn in background..."
  # start as a background process
  uvicorn app.main:app --reload --port 8000 > /tmp/uvicorn.log 2>&1 &
  UV_PID=$!
  echo "uvicorn pid=${UV_PID}"
  # small wait so server is accepting requests
  sleep 2
else
  echo "Server already running on 127.0.0.1:8000"
fi

# 3) prepare payload (we will inline tex)
if [ ! -f "$TEX_FILE" ]; then
  echo "Error: Tex file '$TEX_FILE' not found."
  exit 1
fi

TEX_CONTENT=$(python - <<PY
import sys, json
print(json.dumps(open("${TEX_FILE}","r",encoding="utf-8").read()))
PY
)

# 4) POST to compile endpoint and save PDF
# If you have a JWT token, use Authorization header. Otherwise you may need to temporarily disable auth depend.
AUTH_HEADER=()
if [ -n "$JWT_TOKEN" ]; then
  echo "Using Authorization header"
  AUTH_HEADER=(-H "Authorization: Bearer ${JWT_TOKEN}")
else
  echo "No JWT_TOKEN set; ensure endpoint allows unauthenticated requests for testing or set JWT_TOKEN env var."
fi

echo "Calling ${API_URL}/api/v1/latex/compile-tectonic ..."
curl -sSL -X POST "${API_URL}/api/v1/latex/compile-tectonic" \
  -H "Content-Type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d "{\"tex_source\":${TEX_CONTENT}}" \
  --output "${OUT_PDF}"

if [ -s "${OUT_PDF}" ]; then
  echo "Saved compiled PDF to ${OUT_PDF}"
else
  echo "Compilation likely failed. Printing server logs:"
  tail -n 200 /tmp/uvicorn.log || true
  exit 2
fi

# Cleanup uvicorn if we started it
if [ ! -z "${UV_PID-}" ]; then
  echo "Stopping uvicorn pid ${UV_PID}"
  kill ${UV_PID} || true
fi

echo "Done."
