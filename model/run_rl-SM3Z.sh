#!/usr/bin/env bash
# R40: RL from control S, reward M3 + conditional feasibility (feas 1.0), 400 steps, lockstep, GPU 1. Dev-only
# (no evaluation-set decode): selection between M2 and M3 by the BLOCK4.md R40 rule.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
echo "$(date '+%F %T') rl-SM3Z start (M3 + feas 1.0 from control-S, 400 steps, lockstep, dev-only)" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting M3 --run-name rl-SM3Z --feas 1.0 \
  --base rl/control-S --ctx-run arranger-v2b --steps 400 --windows 16 --group 8 --micro 16 \
  --engine lockstep --workers 24 --val-workers 8 --val-every 100 --n-val 20 > model/logs/rl-SM3Z.log 2>&1
echo "$(date '+%F %T') trained rl-SM3Z: exit $?" >> model/logs/rl_chain.log
