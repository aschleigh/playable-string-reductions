#!/usr/bin/env bash
# rl-A: wait for its training to finish, then decode + evaluate (2 GPU shards).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
while ps -eo args | grep "model.grpo train --setting A --run-name rl-A" | grep -v grep -q; do sleep 60; done
STEP=$($TP -c "import torch; print(torch.load('model/results/rl/rl-A/checkpoint.pt', map_location='cpu')['step'])")
echo "$(date '+%F %T') trained rl-A: checkpoint step $STEP" >> model/logs/rl_chain.log
[ "$STEP" = "800" ] && model/decode_eval.sh rl-A A
