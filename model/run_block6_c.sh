#!/usr/bin/env bash
# BLOCK6 Step 5 (criterion D, frozen in BLOCK6.md): after the dev check of control-J (joint kept unless the strings
# degrade on dev: R63 decision 4) and the checker-v6 piano baseline, decode control-J on the evaluation set (piano,
# solo_flute; plain and masked; melody-first; GPU 1) and evaluate once.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-C] $*" >> "$LOG"; }
until grep -q "\[B6-J\] done" "$LOG" && grep -q "all done" decoding/logs/v6_chain.log; do sleep 60; done
FALLBACK=$($TP - <<'PY'
import json
s = json.load(open("model/results/rl/dev_decode_compare_S2c.json")); j = json.load(open("model/results/rl/dev_decode_compare_J.json"))
S = next(v for k, v in s.items() if "melody-first" in k); J = next(v for k, v in j.items() if "melody-first" in k)
d = json.load(open("model/results/rl/double_stop_stats_mf_J.json"))
bad = any(J[f"val_{r}/top_retention_M"] < S[f"val_{r}/top_retention_M"] - 0.005 for r in ("trio", "duo"))
for r in ("trio", "duo"):
    a, b = d[f"rl/control-S2c | {r}"], d[f"rl/control-J | {r}"]
    bad |= any(b[i]["ds_per_100_notes"] > a[i]["ds_per_100_notes"] + 0.5 for i in a if isinstance(a[i], dict))
print("yes" if bad else "no")
PY
)
say "joint-model fallback needed: $FALLBACK"
if [ "$FALLBACK" = "yes" ]; then say "strings degraded on dev: stop (separate models per BLOCK6 decision 4)"; say done; exit 0; fi
say "start at $(git rev-parse --short HEAD) (tag $(git describe --tags --always))"
OD=model/results/confirm6/control-J/records; mkdir -p $OD
for R in piano solo_flute; do for M in "" "--masked"; do
  SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
  [ -f $OD/${SYS}__$R.jsonl ] && continue
  for s in 0 1 2 3 4 5; do
    CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/control-J/checkpoint.pt \
      --regime $R $M --melody-first --out-dir $OD --shard $s --nshards 6 > model/logs/confirm6_${R}${M}_$s.log 2>&1 &
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
  say "decoded control-J $SYS $R: $?"
done; done
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.confirm6_eval --tested control-J > model/logs/confirm6_eval.log 2>&1
say "evaluated: $?"
say done
