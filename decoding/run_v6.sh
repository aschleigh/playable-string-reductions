#!/usr/bin/env bash
# checker-v6 (R66, piano only): archive the piano masked outputs, regenerate Ou et al. piano masked (GPU 1 only), gate.
cd "$(dirname "$0")/.."
LOG=decoding/logs/v6_chain.log; mkdir -p decoding/logs decoding/results/v6
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
O=headroom/data/out; R=headroom/data/records
[ -d $O/ou_piano_masked_checker-v5 ] || mv $O/ou_piano_masked $O/ou_piano_masked_checker-v5
[ -f $R/ou_piano_masked_checker-v5__piano.jsonl ] || mv $R/ou_piano_masked__piano.jsonl $R/ou_piano_masked_checker-v5__piano.jsonl
say "archived checker-v5 piano masked outputs and records"
decoding/generate_v5.sh piano 0 8
say "generated piano: $(tail -1 decoding/logs/progress.log)"
.venv/bin/python -W ignore -m decoding.gate --regime piano --workers 16 --res decoding/results/v6 > decoding/logs/v6_gate_piano.log 2>&1
say "gate piano exit $? :: $(grep -o '"verdict": "[^"]*"' decoding/results/v6/piano/gate.json)"
say "all done"
