#!/usr/bin/env bash
# BLOCK5 stage C (Step 5, frozen in BLOCK5.md): decode the selected system (and control-S2b) on the evaluation set,
# melody-first, checker-v5, plain and masked -> criterion C evaluation. Runs once.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B5-C] $*" >> "$LOG"; }
until grep -q "\[B5-B\] done" "$LOG"; do sleep 60; done
if grep -q "gate failed" "$LOG"; then say "gate failed: confirming the base against criterion B only"; fi
SEL=$($TP -c "
import json, os
p='model/results/idiom/select_rl.json'
print((json.load(open(p)).get('selected') or 'None').split('/')[-1] if os.path.exists(p) else 'None')")
BASE=$($TP -c "import json; print('control-S2b' if json.load(open('model/results/idiom/select_base.json'))['replace'] else 'control-S2')")
TESTED=$([ "$SEL" = "None" ] && echo $BASE || echo $SEL)
say "start at $(git rev-parse --short HEAD): tested $TESTED, base $BASE"
for NAME in $(echo "$TESTED $BASE" | tr ' ' '\n' | sort -u); do
  CKD=model/results/rl/$NAME; OD=model/results/confirm5/$NAME/records; mkdir -p $OD
  if [ "$NAME" = "control-S2" ]; then mkdir -p model/results/confirm5/control-S2; cp -r model/results/confirm/control-S2/records model/results/confirm5/control-S2/; continue; fi
  for R in trio duo; do for M in "" "--masked"; do
    SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
    [ -f $OD/${SYS}__$R.jsonl ] && continue
    for s in 0 1 2 3 4 5; do
      CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint $CKD/checkpoint.pt --regime $R $M \
        --melody-first --out-dir $OD --shard $s --nshards 6 > model/logs/confirm5_${NAME}_${R}${M}_$s.log 2>&1 &
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
    say "decoded $NAME $SYS $R: $?"
  done; done
done
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.confirm5_eval --tested $TESTED --base $BASE > model/logs/confirm5_eval.log 2>&1
say "evaluated: $?"
say done
