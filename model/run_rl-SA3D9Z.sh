#!/usr/bin/env bash
# R38: RL from control S, setting A3D9 + conditional feasibility (feas 1.0), 400 steps, lockstep engine, GPU 1.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
echo "$(date '+%F %T') rl-SA3D9Z start (A3D9 + feas 1.0 from control-S, 400 steps, lockstep)" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting A3D9 --run-name rl-SA3D9Z --feas 1.0 \
  --base rl/control-S --ctx-run arranger-v2b --steps 400 --windows 16 --group 8 --micro 16 \
  --engine lockstep --workers 24 --val-workers 8 --val-every 100 --n-val 20 > model/logs/rl-SA3D9Z.log 2>&1
rc=$?; echo "$(date '+%F %T') trained rl-SA3D9Z: exit $rc" >> model/logs/rl_chain.log
[ $rc -eq 0 ] && RANGES=detector_ranges_dv2.json NSH=4 model/decode_eval2.sh rl-SA3D9Z A3D9
