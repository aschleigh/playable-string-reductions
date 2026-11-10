#!/usr/bin/env bash
# Block 7 Step 4.3 (R82: both eligible string runs rendered, chosen by ear): review-movement decodes of rl8-S2 / rl8-S4.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [R8-L] $*" >> "$LOG"; }
for RUN in rl8-S2 rl8-S4; do
  OD=model/results/rl/$RUN-review/records; mkdir -p $OD
  for R in trio duo; do for M in "" "--masked"; do
    CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/$RUN/checkpoint.pt \
      --regime $R $M --melody-first --only-review --out-dir $OD > model/logs/$RUN-review_${R}${M}.log 2>&1 &
  done; done
done; wait
say "review decodes: $(ls model/results/rl/rl8-S*-review/records/*.jsonl | wc -l) files"
