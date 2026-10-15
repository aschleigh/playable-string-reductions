#!/usr/bin/env bash
# Block 4 Step 6, detached-safe: RL runs C and A (concurrently), control S, then decode + evaluate each.
# Log: model/logs/rl_chain.log
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; CK=.venv/bin/python; LOG=model/logs/rl_chain.log
STEPS=${STEPS:-800}; W=${W:-24}
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say "start (steps $STEPS, workers $W per run)"
until grep -q "contexts done" model/logs/contexts.log 2>/dev/null; do sleep 60; done
say "contexts ready: $(ls model/results/rl/contexts/arranger-v2b__train.*.pkl | wc -l) shards"

decode_eval() {   # $1 = run dir under model/results/rl, $2.. = settings to evaluate under
  local RUN=$1; shift
  local RD=model/results/rl/$RUN
  for R in trio duo; do
    for M in "" "--masked"; do
      SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
      for s in 0 1 2 3 4 5; do
        CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint $RD/checkpoint.pt --regime $R $M \
          --shard $s --nshards 6 > model/logs/decode_${RUN}_${R}${M}_$s.log 2>&1 &
      done
      wait
      SYS=$SYS R=$R RD=$RD $CK - <<'PY'
import json, os
from arrangement.eval.record import load, save
S, R, RD = os.environ["SYS"], os.environ["R"], os.environ["RD"]
recs, diag = [], []
for s in range(6):
    recs += load(f"{RD}/records/{S}__{R}.{s}.jsonl"); diag += json.load(open(f"{RD}/records/{S}__{R}.{s}.diag.json"))
assert len({r.input_id for r in recs}) == len(recs) == 150, len(recs)
save(sorted(recs, key=lambda r: r.input_id), f"{RD}/records/{S}__{R}.jsonl")
json.dump(diag, open(f"{RD}/records/{S}__{R}.diag.json", "w"), indent=1)
PY
      say "decoded $RUN $SYS $R: $?"
    done
  done
  for ST in "$@"; do
    $CK -W ignore -m model.eval_rl evaluate --run $RUN --setting $ST --suffix "_$ST" > model/logs/eval_rl_${RUN}_$ST.log 2>&1
    say "evaluated $RUN under $ST: $? :: $(grep -o 'success = [A-Za-z]*' model/results/rl/$RUN/eval_$ST.md | tr '\n' ' ')"
  done
}

for ST in C A; do
  ( CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=1 $TP -W ignore -m model.grpo train --setting $ST --run-name rl-$ST \
      --steps $STEPS --windows 16 --group 8 --micro 16 --workers $W --val-every 100 --n-val 20 > model/logs/rl-$ST.log 2>&1
    rc=$?; say "trained rl-$ST: exit $rc"
    [ $rc -eq 0 ] && decode_eval rl-$ST $ST ) &
done
if ! ps -eo args | grep "model.train_s --run-name control-S" | grep -v grep -q && [ ! -f model/results/rl/control-S/checkpoint.pt ]; then
  ( CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.train_s --run-name control-S --steps 3000 > model/logs/control-S.log 2>&1
    say "trained control-S: exit $?" ) &
fi
wait
while ps -eo args | grep "model.train_s --run-name control-S" | grep -v grep -q; do sleep 60; done   # S may run outside this script
[ -f model/results/rl/control-S/checkpoint.pt ] && decode_eval control-S C A
for RUN in rl-C rl-A control-S; do
  $CK -W ignore -m decoding.render_excerpts --idx 67 22 39 42 148 --start 1 60 435 480 6 --model-run rl/$RUN \
    --out decoding/results/examples/$RUN >> model/logs/render_rl.log 2>&1 \
    && $CK -W ignore -m decoding.to_pdf decoding/results/examples/$RUN >> model/logs/render_rl.log 2>&1
  say "rendered $RUN: $?"
done
say "all done"
