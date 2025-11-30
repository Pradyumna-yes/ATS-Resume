#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 file.tex [output.pdf]"
  exit 1
fi

INPUT="$1"
OUT="${2:-${INPUT%.tex}.pdf}"
IMAGE=${TEX_IMAGE:-latex-tectonic:latest}
TMPDIR=$(mktemp -d /tmp/tectonic.XXXX)

cp "$INPUT" "$TMPDIR/resume.tex"

docker run --rm --network none -v "$TMPDIR:/data:Z" "$IMAGE" tectonic /data/resume.tex --outdir /data

cp "$TMPDIR/resume.pdf" "$OUT"
rm -rf "$TMPDIR"
echo "Wrote $OUT"
