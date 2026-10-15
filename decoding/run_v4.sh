#!/usr/bin/env bash
# DECODING.md amendment A3: everything under checker-v4, detached-safe (launch with setsid nohup).
# 1. headroom re-measurement (CPU) -> headroom/results_v4
# 2. per regime: masked generation (GPU), then its gate (CPU, overlapped with the next regime's generation)
cd "$(dirname "$0")/.."
LOG=decoding/logs/v4_chain.log; mkdir -p decoding/logs decoding/results/v4
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
( .venv/bin/python -W ignore -m headroom.measure --workers 16 --out headroom/results_v4 --checker-tag checker-v4 \
    > decoding/logs/v4_measure.log 2>&1; say "measure exit $?" ) &
for R in trio duo solo_violin solo_flute piano; do
  say "generate $R"
  decoding/generate.sh "$R" 4 4
  say "generated $R: $(tail -1 decoding/logs/progress.log)"
  if [ "$R" = trio ]; then
    .venv/bin/python -W ignore -m decoding.render_excerpts --idx 67 22 39 42 148 --start 1 60 435 480 6 \
      --out decoding/results/examples/checker-v4 >> "$LOG" 2>&1 \
      && .venv/bin/python -W ignore -m decoding.to_pdf decoding/results/examples/checker-v4 >> "$LOG" 2>&1
  fi
  ( .venv/bin/python -W ignore -m decoding.gate --regime "$R" --workers 16 --res decoding/results/v4 \
      > "decoding/logs/v4_gate_$R.log" 2>&1; say "gate $R exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v4/$R/gate.json)" ) &
done
wait
say "all done"
