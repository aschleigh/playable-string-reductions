#!/usr/bin/env bash
# DECODING.md amendment A1: everything under checker-v2, detached-safe (launch with setsid nohup).
# 1. headroom re-measurement (CPU) -> headroom/results_v2
# 2. per regime: masked generation (GPU), then its gate (CPU, overlapped with the next regime's generation)
cd "$(dirname "$0")/.."
LOG=decoding/logs/v2_chain.log; mkdir -p decoding/logs decoding/results/v2
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
( .venv/bin/python -W ignore -m headroom.measure --workers 16 --out headroom/results_v2 --checker-tag checker-v2 \
    > decoding/logs/v2_measure.log 2>&1; say "measure exit $?" ) &
for R in trio duo solo_violin solo_flute piano; do
  say "generate $R"
  decoding/generate.sh "$R" 4 6
  say "generated $R: $(tail -1 decoding/logs/progress.log)"
  ( .venv/bin/python -W ignore -m decoding.gate --regime "$R" --workers 16 --res decoding/results/v2 \
      > "decoding/logs/v2_gate_$R.log" 2>&1; say "gate $R exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v2/$R/gate.json)" ) &
done
wait
say "all done"
