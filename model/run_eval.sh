#!/usr/bin/env bash
# Step 5 end to end, detached-safe: decode the final checkpoint (trio, duo; plain and masked),
# then evaluate once the checker-v4 baselines for that regime exist. Log: model/logs/eval.log
cd "$(dirname "$0")/.."
RUN=${RUN:-arranger-v1}; RD=model/results/$RUN; LOG=model/logs/eval.log
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; CK=.venv/bin/python
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
until grep -q '"step": 29999' model/logs/train_$RUN.log && ! pgrep -f "model.train" >/dev/null; do sleep 60; done
say "training done"
for R in trio duo; do
  for M in "" "--masked"; do
    SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
    for s in 0 1 2 3 4 5; do
      [ -f $RD/records/${SYS}__$R.$s.jsonl ] && continue          # shard already done (restart-safe)
      CUDA_VISIBLE_DEVICES=1 $TP -W ignore -m model.decode --checkpoint $RD/checkpoint.pt --regime $R $M \
        --shard $s --nshards 6 > model/logs/decode_${R}${M}_$s.log 2>&1 &   # GPU 0 is full (other users)
    done
    wait
    SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
    SYS=$SYS R=$R RD=$RD $CK - <<'PY'
import json, os
from arrangement.eval.record import load, save
S, R, RD = os.environ["SYS"], os.environ["R"], os.environ["RD"]
recs, diag = [], []
for s in range(6):
    recs += load(f"{RD}/records/{S}__{R}.{s}.jsonl"); diag += json.load(open(f"{RD}/records/{S}__{R}.{s}.diag.json"))
assert len({r.input_id for r in recs}) == len(recs) == 150, (len(recs), len({r.input_id for r in recs}))
save(sorted(recs, key=lambda r: r.input_id), f"{RD}/records/{S}__{R}.jsonl")
json.dump(diag, open(f"{RD}/records/{S}__{R}.diag.json", "w"), indent=1)
PY
    say "decoded $SYS $R: merge exit $?"
  done
done
for R in trio duo; do
  until grep -q "gate $R exit" decoding/logs/v4_chain.log; do sleep 120; done
  $CK -W ignore -m model.evaluate --run $RUN --regimes $R --workers 16 > model/logs/evaluate_$R.log 2>&1
  say "evaluated $R exit $?"
done
say "all done"
