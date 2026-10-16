#!/usr/bin/env bash
# BLOCK5 stage B: Step 1c base decision -> gate check -> RL contexts -> RL MI05, MI10 (GPU 1) -> dev outputs/compare -> selection.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B5-B] $*" >> "$LOG"; }
until grep -q "\[B5-A\] done" "$LOG"; do sleep 60; done
say start
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs arranger-v2b --n-val 61 --workers 16 \
  > model/logs/dev_decode_compare_v2b.log 2>&1
cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_v2b.json
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.block5_select base > model/logs/block5_select_base.log 2>&1
REPLACE=$($TP -c "import json; print(json.load(open('model/results/idiom/select_base.json'))['replace'])")
if [ "$REPLACE" = "True" ]; then BASE=control-S2b; else BASE=control-S2; fi
say "Step 1c: replace=$REPLACE -> base $BASE"
GATE=$($TP -c "import json; print(json.load(open('model/results/idiom/gate_base${BASE#control-}.json'))['PASS'])")
say "gate for base $BASE: $GATE"
if [ "$GATE" != "True" ]; then say "gate failed: no RL (BLOCK5 Step 3)"; say done; exit 0; fi
for s in $(seq 0 15); do
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo contexts --run rl/$BASE --out-name $BASE --split train \
    --shard $s --nshards 16 --greedy-only > model/logs/contexts_${BASE}_$s.log 2>&1 &
done
wait
say "contexts $BASE: $(ls model/results/rl/contexts/${BASE}__train.*.pkl | wc -l) shards"
for S in MI05 MI10; do
  RUN=rl-B5-$S
  [ "$BASE" = "control-S2" ] && RUN=rl-B5o-$S
  CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting $S --run-name $RUN --feas 1.0 \
    --base rl/$BASE --ctx-run $BASE --steps 400 --windows 16 --group 8 --micro 16 \
    --engine lockstep --workers 16 --val-workers 4 --val-every 100 --n-val 20 > model/logs/$RUN.log 2>&1
  say "trained $RUN: exit $?"
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_outputs --runs rl/$RUN --workers 16 > model/logs/dev_outputs_$RUN.log 2>&1
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/$RUN --n-val 61 --workers 16 \
    > model/logs/dev_decode_compare_$RUN.log 2>&1
  cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_$RUN.json
  say "dev decodes $RUN: $?"
done
P=rl-B5; [ "$BASE" = "control-S2" ] && P=rl-B5o
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.block5_select rl --base rl/$BASE --runs rl/$P-MI05 rl/$P-MI10 \
  > model/logs/block5_select_rl.log 2>&1
say "selection: $? :: $(tail -c 300 model/logs/block5_select_rl.log | tr '\n' ' ')"
say done
