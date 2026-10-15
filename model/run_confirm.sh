#!/usr/bin/env bash
# R46 confirmatory test: decode control-S2, arranger-v2b, control-S (melody-first, checker-v5) -> evaluate.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; CK=.venv/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [confirm] $*" >> "$LOG"; }
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
for spec in "control-S2 model/results/rl/control-S2" "arranger-v2b model/results/arranger-v2b" "control-S model/results/rl/control-S"; do
  set -- $spec; NAME=$1; CKD=$2; OD=model/results/confirm/$NAME/records; mkdir -p $OD
  for R in trio duo; do for M in "" "--masked"; do
    SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
    [ -f $OD/${SYS}__$R.jsonl ] && continue
    for s in 0 1 2 3 4 5; do
      CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint $CKD/checkpoint.pt --regime $R $M \
        --melody-first --out-dir $OD --shard $s --nshards 6 > model/logs/confirm_${NAME}_${R}${M}_$s.log 2>&1 &
    done; wait
    SYS=$SYS R=$R OD=$OD $CK - <<'PY'
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
    say "decoded $NAME $SYS $R: $?"
  done; done
done
$CK -W ignore -m model.confirm_eval > model/logs/confirm_eval.log 2>&1
say "evaluated: $?"
