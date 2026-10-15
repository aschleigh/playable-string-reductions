#!/usr/bin/env bash
# R36: RL from control S, setting A2 (A + "kept" needs >= 75% of the written duration) + conditional
# feasibility term (feas 1.0), 400 steps, lockstep engine, GPU 1.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
echo "$(date '+%F %T') rl-SA2Z start (A2 + feas 1.0 from control-S, 400 steps, lockstep)" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting A2 --run-name rl-SA2Z --feas 1.0 \
  --base rl/control-S --ctx-run arranger-v2b --steps ${STEPS:-400} --windows 16 --group 8 --micro 16 \
  --engine lockstep --workers 24 --val-workers 12 --val-every 100 --n-val 20 > model/logs/rl-SA2Z.log 2>&1
rc=$?; echo "$(date '+%F %T') trained rl-SA2Z: exit $rc" >> model/logs/rl_chain.log
[ $rc -eq 0 ] && model/decode_eval.sh rl-SA2Z A2
