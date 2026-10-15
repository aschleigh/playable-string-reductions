#!/usr/bin/env bash
# R44: S2 targets (full train split) -> fine-tune control-S2 from v2b -> dev evaluation (melody-first decoding).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [S2] $*" >> "$LOG"; }
say start
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.targets_s2 --workers 32 > model/logs/targets_s2.log 2>&1
say "targets built: $? :: $(tail -2 model/logs/targets_s2.log | cut -c1-200 | tr '\n' ' ')"
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-S2 --targets s2 --steps 3000 \
  > model/logs/control-S2.log 2>&1
say "control-S2 trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.double_stop_stats --melody-first \
  --runs arranger-v2b rl/control-S rl/control-S2 > model/logs/double_stop_stats.log 2>&1
say "double-stop stats: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/control-S2 --n-val 61 \
  > model/logs/dev_decode_compare_S2.log 2>&1
cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_S2.json
say "dev compare: $?"
say "done"
