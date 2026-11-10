#!/usr/bin/env bash
# BLOCK6 Step 6: control-FK2 review-movement decodes (piano, solo flute) -> MusicXML excerpts (R61: MusicXML only).
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B6-L2] $*" >> "$LOG"; }
OD=model/results/rl/control-FK2-review/records; mkdir -p $OD
for R in piano solo_flute; do for M in "" "--masked"; do
  CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=2 $TP -W ignore -m model.decode --checkpoint model/results/rl/control-FK2/checkpoint.pt \
    --regime $R $M --melody-first --only-review --out-dir $OD > model/logs/control-FK2-review_${R}${M}.log 2>&1
done; done
say "review decodes: $(ls $OD/*.jsonl | wc -l) files"
for R in piano solo_flute; do
  CUDA_VISIBLE_DEVICES="" .venv/bin/python -W ignore -m decoding.render_excerpts --idx 22 67 --start 60 1 --bars 16 \
    --model-run rl/control-FK2-review --regime $R --out decoding/results/examples/control-FK2-$R > model/logs/render_FK_$R.log 2>&1
  CUDA_VISIBLE_DEVICES="" .venv/bin/python -W ignore -m decoding.render_excerpts --idx 22 --start 1 --bars 162 \
    --model-run rl/control-FK2-review --regime $R --out decoding/results/examples/control-FK2-$R-full >> model/logs/render_FK_$R.log 2>&1
  say "rendered $R: $?"
done
say done
