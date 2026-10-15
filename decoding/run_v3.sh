#!/usr/bin/env bash
# DECODING.md amendment A2: everything under checker-v3, detached-safe (launch with setsid nohup).
# 1. headroom re-measurement (CPU) -> headroom/results_v3
# 2. per regime: masked generation (GPU), then its gate (CPU, overlapped with the next regime's generation)
cd "$(dirname "$0")/.."
LOG=decoding/logs/v3_chain.log; mkdir -p decoding/logs decoding/results/v3
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
( .venv/bin/python -W ignore -m headroom.measure --workers 16 --out headroom/results_v3 --checker-tag checker-v3 \
    > decoding/logs/v3_measure.log 2>&1; say "measure exit $?" ) &
for R in trio duo solo_violin solo_flute piano; do
  say "generate $R"
  decoding/generate.sh "$R" 4 6
  say "generated $R: $(tail -1 decoding/logs/progress.log)"
  [ "$R" = trio ] && .venv/bin/python -W ignore -m decoding.render_masked --idx 67 --bars 1-16 \
      >> "$LOG" 2>&1
  ( .venv/bin/python -W ignore -m decoding.gate --regime "$R" --workers 16 --res decoding/results/v3 \
      > "decoding/logs/v3_gate_$R.log" 2>&1; say "gate $R exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v3/$R/gate.json)" ) &
done
wait
say "all done"
