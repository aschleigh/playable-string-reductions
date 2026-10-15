#!/usr/bin/env bash
# R35 (exploratory): setting A from control S plus the conditional feasibility term (feas 1.0), 400 steps, GPU 1.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
echo "$(date '+%F %T') rl-SAZ start (setting A + feas 1.0 from control-S, 400 steps)" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting A --run-name rl-SAZ --base rl/control-S \
  --ctx-run arranger-v2b --feas 1.0 --steps ${STEPS:-400} --windows 16 --group 8 --micro 8 --workers 24 --val-every 100 --n-val 20 \
  > model/logs/rl-SAZ.log 2>&1
rc=$?; echo "$(date '+%F %T') trained rl-SAZ: exit $rc" >> model/logs/rl_chain.log
[ $rc -eq 0 ] && model/decode_eval.sh rl-SAZ A
