#!/usr/bin/env bash
# Block 4 Step 1 diagnostics (read-only). Log: model/logs/diagnose.log
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/diagnose.log
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
say start
( for R in trio duo quartet; do CUDA_VISIBLE_DEVICES="" $TP -W ignore -m model.diagnose cpu --regime $R --workers 12 \
    > model/logs/diagnose_cpu_$R.log 2>&1; say "cpu $R exit $?"; done ) &
for M in arranger oracle; do for R in trio duo; do
  for s in 0 1 2 3 4 5; do
    CUDA_VISIBLE_DEVICES=1 $TP -W ignore -m model.diagnose decode --regime $R --mode $M --shard $s --nshards 6 \
      > model/logs/diagnose_${M}_${R}_$s.log 2>&1 &
  done; wait -n; wait $(jobs -p | tail -6) 2>/dev/null; say "decode $M $R done: $(ls model/results/diagnostics/decode/${M}__$R.*.pkl | wc -l)/6"
done; done
wait
CUDA_VISIBLE_DEVICES="" $TP -W ignore -m model.diagnose report --workers 16 > model/logs/diagnose_report.log 2>&1
say "report exit $?"
