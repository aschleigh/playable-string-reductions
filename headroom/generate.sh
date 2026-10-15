#!/usr/bin/env bash
# Generate every neural-system output (DECISION.md A1). Idempotent: existing
# outputs are skipped. Usage: headroom/generate.sh [workers_gpu0] [workers_gpu1]
set -u
cd "$(dirname "$0")/.."
PY=/scratch/ashleyz/headroom_models/env_m2m/bin/python
# Weights cached on /scratch: AFS home needs a login token that detached jobs lose.
export HF_HOME=/scratch/ashleyz/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
W0=${1:-6}; W1=${2:-12}; N=$((W0 + W1))
JOBS="ou_band:trio amt:trio ou_band:duo ou_band:solo_violin ou_band:solo_flute ou_piano:piano"
mkdir -p headroom/data/logs
for w in $(seq 0 $((N - 1))); do
  gpu=$([ "$w" -lt "$W0" ] && echo 0 || echo 1)
  (
    for job in $JOBS; do
      CUDA_VISIBLE_DEVICES=$gpu $PY headroom/run_models.py --system "${job%%:*}" --regime "${job##*:}" \
        --shard "$w" --nshards "$N" >> "headroom/data/logs/worker_$w.log" 2>&1
    done
  ) &
done
wait
