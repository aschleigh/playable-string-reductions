#!/usr/bin/env bash
# R79 (Block 7 + Block 6 Amendment A, merged; reward R8): gate -> contexts -> RL runs (GPU 1 only, <= 16 CPU) -> dev decodes.
cd "$(dirname "$0")/.."
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [R8] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.reward_gate --workers 16 > model/logs/reward_gate.log 2>&1
GATE=$($TP -c "import json; print(json.load(open('model/results/rl/reward_gate.json'))['PASS'])")
say "reward gate: $GATE"
if [ "$GATE" != "True" ]; then say "gate failed: stop for a reward redesign (BLOCK7 Step 2)"; say done; exit 0; fi
for spec in "control-S2c trio duo" "control-FK2 solo_flute piano"; do
  set -- $spec; RUN=$1; shift
  [ $(ls model/results/rl/contexts/${RUN}__train.*.pkl 2>/dev/null | wc -l) -ge 16 ] && continue
  for s in $(seq 0 15); do
    CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo contexts --run rl/$RUN --out-name $RUN --split train \
      --shard $s --nshards 16 --greedy-only --melody-first --regimes "$@" > model/logs/contexts_${RUN}_$s.log 2>&1 &
  done; wait
  say "contexts $RUN: $(ls model/results/rl/contexts/${RUN}__train.*.pkl | wc -l) shards"
done
run() {  # name setting base ctx regimes steps windows feas
  local NAME=$1 S=$2 B=$3 C=$4 RG=$5 ST=$6 WN=$7 FE=$8
  [ -f model/results/rl/$NAME/checkpoint.pt ] && { say "skip $NAME (done)"; return; }
  CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting $S --run-name $NAME --base rl/$B \
    --ctx-run $C --regimes $RG --steps $ST --windows $WN --group 8 --micro 16 --feas $FE --lr 1e-5 --beta 0.02 \
    --engine lockstep --workers 12 --val-workers 4 --val-every 100 --n-val 20 > model/logs/$NAME.log 2>&1
  say "trained $NAME: exit $?"
}
run rl8-F05 R8F05 control-FK2 control-FK2 solo_flute 1000 32 1.0
run rl8-F10 R8F10 control-FK2 control-FK2 solo_flute 1000 32 1.0
run rl8-K1 R8K control-FK2 control-FK2 piano 1000 32 1.0
run rl8-K3 R8K control-FK2 control-FK2 piano 1000 32 3.0
run rl8-S2 R8S2 control-S2c control-S2c "trio duo" 400 16 1.0
run rl8-S4 R8S4 control-S2c control-S2c "trio duo" 400 16 1.0
for R in rl8-F05 rl8-F10 rl8-K1 rl8-K3; do
  [ -f model/results/rl/$R/checkpoint.pt ] && CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_fk --runs rl/$R \
    --workers 16 > model/logs/dev_fk_$R.log 2>&1
done
say "dev flute/piano decodes done"
for R in rl8-S2 rl8-S4; do
  [ -f model/results/rl/$R/checkpoint.pt ] || continue
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_decode_compare --runs rl/$R --n-val 61 --workers 16 \
    > model/logs/dev_decode_compare_$R.log 2>&1
  cp model/results/rl/dev_decode_compare.json model/results/rl/dev_decode_compare_$R.json
done
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.double_stop_stats --melody-first --workers 16 \
  --runs rl/control-S2c rl/rl8-S2 rl/rl8-S4 > model/logs/double_stop_stats_rl8.log 2>&1
cp model/results/rl/double_stop_stats_mf.json model/results/rl/double_stop_stats_mf_rl8.json
say "dev strings decodes done"
say done
