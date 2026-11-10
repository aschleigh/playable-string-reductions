#!/usr/bin/env bash
# checker-v8 (R83, piano only): archive the piano masked outputs, regenerate Ou et al. piano masked (GPU 1 only), gate.
cd "$(dirname "$0")/.."
LOG=decoding/logs/v8_chain.log; mkdir -p decoding/logs decoding/results/v8
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
O=headroom/data/out; R=headroom/data/records
[ -d $O/ou_piano_masked_checker-v7 ] || mv $O/ou_piano_masked $O/ou_piano_masked_checker-v7
[ -f $R/ou_piano_masked_checker-v7__piano.jsonl ] || mv $R/ou_piano_masked__piano.jsonl $R/ou_piano_masked_checker-v7__piano.jsonl
say "archived checker-v7 piano masked outputs and records"
decoding/generate_v5.sh piano 0 8
say "generated piano: $(tail -1 decoding/logs/progress.log)"
.venv/bin/python -W ignore -m decoding.gate --regime piano --workers 16 --res decoding/results/v8 > decoding/logs/v8_gate_piano.log 2>&1
say "gate piano exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v8/piano/gate.json)"
say "all done"
