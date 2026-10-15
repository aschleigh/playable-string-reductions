#!/usr/bin/env bash
# Reproduce the headroom measurement end to end (DECISION.md, amendment A1).
# Checker environment: .venv (requirements-lock.txt). Model environment: headroom/env.md.
# Run from a checkout of tag checker-v1.1 or later with an unchanged checker.
set -euo pipefail
cd "$(dirname "$0")/.."
git diff --quiet checker-v1.1 -- arrangement/checker arrangement/config/instruments.yaml arrangement/assign.py \
  || { echo "checker or config differs from checker-v1.1; refusing to measure" >&2; exit 1; }
CK=.venv/bin/python
$CK -W ignore -m headroom.sources --workers 24     # 1. evaluation set (seeded) -> headroom/data/sources
headroom/generate.sh "${W0:-6}" "${W1:-12}"         # 2. neural outputs (GPU)   -> headroom/data/out
$CK -W ignore -m headroom.measure --workers 32     # 3. check + statistics     -> headroom/results
$CK -m headroom.figure
$CK -m headroom.report                              # 4. HEADROOM.md
tar -czf headroom/results/outputs.tar.gz -C headroom/data out eval_set.json
