#!/usr/bin/env bash
# BLOCK6 Step 3 (R63): joint arranger control-J (trio, duo: S2c targets; flute, piano: F/K targets), from control-S2c.
# Then the dev evaluation: strings (dev_decode_compare, double stops) and flute/piano (dev_fk, with targets/top line).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-J] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-J --base rl/control-S2c --targets joint \
  --steps 3000 > model/logs/control-J.log 2>&1
say "control-J trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_fk --runs rl/control-J --targets --workers 16 > model/logs/dev_fk_J.log 2>&1
say "dev flute/piano: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.double_stop_stats --melody-first --workers 16 \
  --runs rl/control-S2c rl/control-J > model/logs/double_stop_stats_J.log 2>&1
cp model/results/rl/double_stop_stats_mf.json model/results/rl/double_stop_stats_mf_J.json
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/control-J --n-val 61 --workers 16 \
  > model/logs/dev_decode_compare_J.log 2>&1
cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_J.json
say "dev strings: $?"
say done
