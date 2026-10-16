#!/usr/bin/env bash
# R58: control-S2c (viola gap 1 quarter) -> dev double stops (S2, S2b, S2c) and dev compare -> review-movement decodes.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [S2c] $*" >> "$LOG"; }
until [ -f model/results/rl/targets_s2c__train.pkl ] && grep -q "^duo" model/results/rl/logs/targets_s2c.log; do sleep 30; done
say start
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-S2c --targets s2c --steps 3000 \
  > model/logs/control-S2c.log 2>&1
say "control-S2c trained: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.double_stop_stats --melody-first --workers 16 \
  --runs rl/control-S2 rl/control-S2b rl/control-S2c > model/logs/double_stop_stats_S2c.log 2>&1
cp model/results/rl/double_stop_stats_mf.json model/results/rl/double_stop_stats_mf_S2c.json
say "double-stop stats: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/control-S2c --n-val 61 --workers 16 \
  > model/logs/dev_decode_compare_S2c.log 2>&1
cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_S2c.json
say "dev compare: $?"
OD=model/results/rl/control-S2c-review/records; mkdir -p $OD
for R in trio duo; do for M in "" "--masked"; do
  CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/control-S2c/checkpoint.pt \
    --regime $R $M --melody-first --only-review --out-dir $OD > model/logs/control-S2c-review_${R}${M}.log 2>&1
done; done
say "review decodes: $(ls $OD/*.jsonl | wc -l) files"
say done
