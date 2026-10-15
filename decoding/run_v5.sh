#!/usr/bin/env bash
# DECODING.md amendment A4: checker-v5 re-run (GPU 1 only). Log: decoding/logs/v5_chain.log
cd "$(dirname "$0")/.."
LOG=decoding/logs/v5_chain.log; mkdir -p decoding/logs decoding/results/v5
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
( .venv/bin/python -W ignore -m headroom.measure --workers 12 --out headroom/results_v5 --checker-tag checker-v5 \
    > decoding/logs/v5_measure.log 2>&1; say "measure exit $?" ) &
( .venv/bin/python -W ignore -m decoding.repair --regimes trio duo solo_violin --workers 12 > decoding/logs/v5_repair.log 2>&1
  say "repair exit $?" ) &
for R in trio duo solo_violin; do
  say "generate $R"
  decoding/generate_v5.sh "$R" 0 8
  say "generated $R: $(tail -1 decoding/logs/progress.log)"
  ( .venv/bin/python -W ignore -m decoding.gate --regime "$R" --workers 12 --res decoding/results/v5 \
      > "decoding/logs/v5_gate_$R.log" 2>&1; say "gate $R exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v5/$R/gate.json)" ) &
done
wait
say "all done"
