#!/usr/bin/env bash
# checker-v5 copy of generate.sh: GPU 1 only (shared machine; agreed with the GPU 0 user)
cd "$(dirname "$0")/.."
export HF_HOME=/scratch/ashleyz/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PY=/scratch/ashleyz/headroom_models/env_m2m/bin/python
R=${1:-trio}; W0=${2:-4}; W1=${3:-6}
mkdir -p decoding/logs
for pass in 1 2 3; do
  N=$((W0 + W1))
  for w in $(seq 0 $((N - 1))); do
    gpu=$([ "$w" -lt "$W0" ] && echo 0 || echo 1)
    CUDA_VISIBLE_DEVICES=$gpu $PY decoding/run_constrained.py --regime "$R" --shard "$w" --nshards "$N" \
      >> "decoding/logs/${R}_pass${pass}_w$w.log" 2>&1 &
  done
  wait
  B=$([ "$R" = piano ] && echo ou_piano || echo ou_band)
  n=$(ls headroom/data/out/${B}_masked/$R/*.json 2>/dev/null | wc -l)
  echo "$(date) $R pass $pass: $n/150" >> decoding/logs/progress.log
  [ "$n" -ge 150 ] && break
  W0=0; W1=6
done
