#!/usr/bin/env bash
# BLOCK6 Step 5 for control-FK2 (R82): the flute half of criterion D now (the user approved the flute excerpts); piano
# waits for the thinner-target fix. Decode on the evaluation set (plain and masked; melody-first; GPU 1), evaluate once.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-C2] $*" >> "$LOG"; }
T=${T:-control-FK2}; REGIMES=${REGIMES:-solo_flute}
say "start $T $REGIMES at $(git rev-parse --short HEAD)"
OD=model/results/confirm6/$T/records; mkdir -p $OD
for R in $REGIMES; do for M in "" "--masked"; do
  SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
  [ -f $OD/${SYS}__$R.jsonl ] && continue
  for s in 0 1 2 3 4 5; do
    CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/$T/checkpoint.pt \
      --regime $R $M --melody-first --out-dir $OD --shard $s --nshards 6 > model/logs/confirm6_${T}_${R}${M}_$s.log 2>&1 &
  done; wait
  SYS=$SYS R=$R OD=$OD $TP - <<'PY'
import json, os
from arrangement.eval.record import load, save
S, R, OD = os.environ["SYS"], os.environ["R"], os.environ["OD"]
recs, diag = [], []
for s in range(6):
    recs += load(f"{OD}/{S}__{R}.{s}.jsonl"); diag += json.load(open(f"{OD}/{S}__{R}.{s}.diag.json"))
assert len({r.input_id for r in recs}) == len(recs) == 150
save(sorted(recs, key=lambda r: r.input_id), f"{OD}/{S}__{R}.jsonl")
json.dump(diag, open(f"{OD}/{S}__{R}.diag.json", "w"), indent=1)
PY
  say "decoded $T $SYS $R: $?"
done; done
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.confirm6_eval --tested $T --regimes $REGIMES > model/logs/confirm6_eval_${T}_${REGIMES// /_}.log 2>&1
say "evaluated: $?"
say done
