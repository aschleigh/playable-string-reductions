#!/usr/bin/env bash
# R70: F3 targets with the CUT realisation (targets_fk2) -> control-FK2 (n_real 6, from control-S2c; flute + piano) -> dev check.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-FK2] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD)"
CUDA_VISIBLE_DEVICES="" $TP -W ignore -m model.targets_fk --workers 16 --breath 3 --tag 2 > model/results/rl/logs/targets_fk2.log 2>&1
say "targets fk2: $? :: $(tail -2 model/results/rl/logs/targets_fk2.log | cut -c1-300 | tr '\n' ' ')"
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-FK2 --base rl/control-S2c --targets fk2 \
  --n-real 6 --steps 3000 > model/logs/control-FK2.log 2>&1
say "control-FK2 trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_fk --runs rl/control-FK2 --workers 16 > model/logs/dev_fk_FK2.log 2>&1
say "dev flute/piano: $?"
say done
