#!/usr/bin/env bash
# Evaluate a running GRPO run at an intermediate checkpoint, without stopping it.
# Usage: snapshot_eval.sh RUN STEP SETTING   -> model/results/rl/RUN-sSTEP (decode + evaluate)
cd "$(dirname "$0")/.."
RUN=$1; STEP=$2; ST=$3; SRC=model/results/rl/$RUN; DST=model/results/rl/$RUN-s$STEP
TP=/scratch/ashleyz/headroom_models/env_train/bin/python
until grep -q "^$STEP," $SRC/log.csv 2>/dev/null; do sleep 60; done     # the checkpoint saved at step STEP's validation
mkdir -p $DST
$TP - <<PY
import torch, shutil
ck = torch.load("$SRC/checkpoint.pt", map_location="cpu")
assert ck["step"] == $STEP, ck["step"]
ck["cfg"] = {**ck["cfg"], "run_name": "$RUN-s$STEP"}
torch.save(ck, "$DST/checkpoint.pt")
shutil.copy("$SRC/log.csv", "$DST/log_at_snapshot.csv")
PY
echo "$(date '+%F %T') snapshot $RUN at step $STEP: $?" >> model/logs/rl_chain.log
model/decode_eval.sh $RUN-s$STEP $ST
