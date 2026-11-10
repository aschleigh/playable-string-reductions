#!/usr/bin/env bash
# BLOCK6 decision 4 fallback (R68): control-FK (flute + piano only, from control-S2c); strings stay control-S2c.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-FK] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD)"
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-FK --base rl/control-S2c --targets fk \
  --steps 3000 > model/logs/control-FK.log 2>&1
say "control-FK trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_fk --runs rl/control-FK --workers 16 > model/logs/dev_fk_FK.log 2>&1
say "dev flute/piano: $?"
say done
