#!/usr/bin/env bash
# Decode a finished Block 4 run (trio, duo; plain and masked) and evaluate it. Usage: decode_eval.sh RUN SETTING...
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; CK=.venv/bin/python; LOG=model/logs/rl_chain.log
NSH=${NSH:-2}   # decode shards on GPU 1 (shared with RL learners and other users: keep memory low)
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
decode_eval() {   # $1 = run dir under model/results/rl, $2.. = settings to evaluate under
  local RUN=$1; shift
  local RD=model/results/rl/$RUN
  for R in trio duo; do
    for M in "" "--masked"; do
      SYS=$([ -z "$M" ] && echo arranger || echo arranger_masked)
      for s in $(seq 0 $((NSH - 1))); do
        CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint $RD/checkpoint.pt --regime $R $M \
          --shard $s --nshards $NSH > model/logs/decode_${RUN}_${R}${M}_$s.log 2>&1 &
      done
      wait
      SYS=$SYS R=$R RD=$RD NSH=$NSH $CK - <<'PY'
import json, os
from arrangement.eval.record import load, save
S, R, RD, N = os.environ["SYS"], os.environ["R"], os.environ["RD"], int(os.environ["NSH"])
recs, diag = [], []
for s in range(N):
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

decode_eval "$@"
