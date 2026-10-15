#!/usr/bin/env bash
# R33: RL (setting A) starting from control S, once rl-A's learner frees GPU 1 and its CPU workers.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
while ps -eo args | grep "model.grpo train --setting A --run-name rl-A " | grep -v grep -q; do sleep 60; done
echo "$(date '+%F %T') rl-SA start (setting A from control-S, 400 steps)" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting A --run-name rl-SA --base rl/control-S \
  --ctx-run arranger-v2b --steps ${STEPS:-400} --windows 16 --group 8 --micro 8 --workers 24 --val-every 100 --n-val 20 \
  > model/logs/rl-SA.log 2>&1
rc=$?; echo "$(date '+%F %T') trained rl-SA: exit $rc" >> model/logs/rl_chain.log
[ $rc -eq 0 ] && model/decode_eval.sh rl-SA A
