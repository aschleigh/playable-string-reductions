#!/usr/bin/env bash
# control S: wait for its training (started by the first chain), then decode + evaluate under C and A.
cd "$(dirname "$0")/.."
while ps -eo args | grep "model.train_s --run-name control-S" | grep -v grep -q; do sleep 60; done
[ -f model/results/rl/control-S/checkpoint.pt ] && model/decode_eval.sh control-S C A
