#!/usr/bin/env bash
# BLOCK5 Step 1b/1c (R49, R51): fine-tune control-S2b from v2b on the S2b targets -> dev evaluation (melody-first).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [S2b] $*" >> "$LOG"; }
say start
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-S2b --targets s2b --steps 3000 \
  > model/logs/control-S2b.log 2>&1
say "control-S2b trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.double_stop_stats --melody-first --workers 16 \
  --runs rl/control-S2 rl/control-S2b > model/logs/double_stop_stats_S2b.log 2>&1
cp model/results/rl/double_stop_stats_mf.json model/results/rl/double_stop_stats_mf_S2b.json
say "double-stop stats: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/control-S2b --n-val 61 --workers 16 \
  > model/logs/dev_decode_compare_S2b.log 2>&1
cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_S2b.json
say "dev compare: $?"
say "done"
