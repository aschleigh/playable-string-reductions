#!/usr/bin/env bash
# REVIEW R37: decode v2 (unisons merged at commit time). Keep decode-v1 outputs; re-decode the reference (v2b),
# refresh the METRICS 1.4.0 copies, recompute detector ranges under decode v2, then re-decode + re-evaluate runs.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; CK=.venv/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [dv2] $*" >> "$LOG"; }
keep_v1() {   # $1 = run dir
  [ -d $1/records ] && [ ! -d $1/records_dv1 ] && mv $1/records $1/records_dv1
  for f in $1/eval_*.json $1/eval_*.md; do [ -f "$f" ] && case "$f" in *_dv1.*) ;; *) mv "$f" "${f%.*}_dv1.${f##*.}";; esac; done
  [ -d $1/eval ] && [ ! -d $1/eval_dv1 ] && mv $1/eval $1/eval_dv1
}
say start
keep_v1 model/results/arranger-v2b
for R in trio duo; do for M in "" "--masked"; do
  SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
  for s in 0 1 2 3 4 5; do
    CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/arranger-v2b/checkpoint.pt \
      --regime $R $M --shard $s --nshards 6 > model/logs/dv2_v2b_${R}${M}_$s.log 2>&1 &
  done; wait
  SYS=$SYS R=$R $CK - <<'PY'
import json, os
from arrangement.eval.record import load, save
S, R, RD = os.environ["SYS"], os.environ["R"], "model/results/arranger-v2b"
recs, diag = [], []
for s in range(6):
    recs += load(f"{RD}/records/{S}__{R}.{s}.jsonl"); diag += json.load(open(f"{RD}/records/{S}__{R}.{s}.diag.json"))
assert len({r.input_id for r in recs}) == len(recs) == 150
save(sorted(recs, key=lambda r: r.input_id), f"{RD}/records/{S}__{R}.jsonl")
json.dump(diag, open(f"{RD}/records/{S}__{R}.diag.json", "w"), indent=1)
PY
  say "decoded arranger-v2b $SYS $R: $?"
done; done
mkdir -p model/results/metrics-1.4.0/dv1
for R in trio duo; do
  [ -d model/results/metrics-1.4.0/dv1/$R ] || cp -r model/results/metrics-1.4.0/$R model/results/metrics-1.4.0/dv1/$R
  rm -f model/results/metrics-1.4.0/$R/records/arranger-v2b*__$R.jsonl
done
$CK -W ignore -m model.rerun_baselines --regimes trio duo --workers 24 > model/logs/dv2_rerun.log 2>&1; say "metrics-1.4.0 trio/duo re-scored with v2b decode v2: $?"
$CK -W ignore -m model.eval_rl ranges --out detector_ranges_dv2.json > model/logs/dv2_ranges.log 2>&1; say "detector ranges (decode v2) written: $?"
for spec in "control-S C A" "rl-A A" "rl-SA A" "rl-C C"; do
  set -- $spec; RUN=$1; shift
  keep_v1 model/results/rl/$RUN
  RANGES=detector_ranges_dv2.json NSH=6 model/decode_eval2.sh $RUN "$@"
done
say "re-decoded control-S, rl-A, rl-SA, rl-C"
# runs launched just before the decode change: decode them under v2 only (rl-SAZ's partial mixed decode was
# stopped and set aside; rl-SA2Z is still training)
RANGES=detector_ranges_dv2.json NSH=6 model/decode_eval2.sh rl-SAZ A
while ps -eo args | grep "run-name rl-SA2Z" | grep -v grep -q; do sleep 60; done
STEP=$($TP -c "import torch; print(torch.load('model/results/rl/rl-SA2Z/checkpoint.pt', map_location='cpu')['step'])")
say "rl-SA2Z training ended at checkpoint step $STEP"
[ "$STEP" = "400" ] && RANGES=detector_ranges_dv2.json NSH=6 model/decode_eval2.sh rl-SA2Z A2
say "all done"
