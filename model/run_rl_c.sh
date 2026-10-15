#!/usr/bin/env bash
# rl-C restarted on GPU 0 (GPU 1 full: OOM at step 2), then decode + evaluate.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
echo "$(date '+%F %T') rl-C restart on GPU 0" >> model/logs/rl_chain.log
CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting C --run-name rl-C \
  --steps ${STEPS:-800} --windows 16 --group 8 --micro 8 --workers 24 --val-every 100 --n-val 20 > model/logs/rl-C.log 2>&1
rc=$?; echo "$(date '+%F %T') trained rl-C: exit $rc" >> model/logs/rl_chain.log
[ $rc -eq 0 ] && model/decode_eval.sh rl-C C
