#!/usr/bin/env bash
# Window contexts + oracle-under-mask labels for the GRPO train split, on single-thread CPU processes.
cd "$(dirname "$0")/.."
N=${N:-34}
for s in $(seq 0 $((N-1))); do
  CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 /scratch/ashleyz/headroom_models/env_train/bin/python -W ignore \
    -m model.grpo contexts --run arranger-v2b --split train --shard $s --nshards $N > model/logs/contexts_$s.log 2>&1 &
done
wait
echo "$(date '+%F %T') contexts done: $(ls model/results/rl/contexts/*.pkl | wc -l) shards" >> model/logs/contexts.log
