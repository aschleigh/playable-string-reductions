#!/usr/bin/env bash
# R82: checker-v7 (piano hand span 12) -> K2 piano targets (targets_fk3) -> control-FK3 (from control-S2c, as control-FK2)
# -> dev check -> review decodes (piano) ; then Ou et al. piano re-masked under checker-v7 (GPU 1).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-FK3] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
for S in train val; do
  CUDA_VISIBLE_DEVICES="" $TP -W ignore -m model.targets_fk --workers 16 --breath 3 --piano-k2 --tag 3 --split $S > model/results/rl/logs/targets_fk3_$S.log 2>&1
  say "targets fk3 $S: $? :: $(grep '^piano' model/results/rl/logs/targets_fk3_$S.log | cut -c1-400)"
done
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-FK3 --base rl/control-S2c --targets fk3 \
  --n-real 6 --steps 3000 > model/logs/control-FK3.log 2>&1
say "control-FK3 trained: $?"
OD=model/results/rl/control-FK3-review/records; mkdir -p $OD
for M in "" "--masked"; do
  CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/control-FK3/checkpoint.pt \
    --regime piano $M --melody-first --only-review --out-dir $OD > model/logs/control-FK3-review_piano${M}.log 2>&1 &
done
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_fk --runs rl/control-FK2 rl/control-FK3 --workers 14 > model/logs/dev_fk_FK3.log 2>&1
say "dev flute/piano (checker-v7): $?"
wait
say "review decodes: $(ls $OD/*.jsonl | wc -l) files"
say done
