#!/usr/bin/env bash
# BLOCK5 stage A: wait for control-S2b (run_s2b.sh) and P -> calibrate P -> dev outputs of control-S2b -> gate.
cd "$(dirname "$0")/.."
TP=/scratch/ashleyz/headroom_models/env_train/bin/python; LOG=model/logs/rl_chain.log
say() { echo "$(date '+%F %T') [B5-A] $*" >> "$LOG"; }
say "waiting for control-S2b chain, P and the first dev dump"
until grep -q "\[S2b\] done" "$LOG" && [ -f model/results/idiom/P/checkpoint.pt ] && [ -f model/results/idiom/dev_outputs/rl_rl-AZ2.pkl ]; do sleep 60; done
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.idiom calibrate > model/logs/idiom_calib.log 2>&1
say "P calibrated: $?"
CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 $TP -W ignore -m model.dev_outputs --runs rl/control-S2b --workers 16 > model/logs/dev_outputs_2.log 2>&1
say "dev outputs control-S2b: $?"
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.idiom_gate --base rl/control-S2b --others rl/control-S2 > model/logs/idiom_gate.log 2>&1
cp model/results/idiom/gate.json model/results/idiom/gate_baseS2b.json; cp model/results/idiom/gate.md model/results/idiom/gate_baseS2b.md
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 $TP -W ignore -m model.idiom_gate --base rl/control-S2 --others rl/control-S2b > model/logs/idiom_gate_S2.log 2>&1
cp model/results/idiom/gate.json model/results/idiom/gate_baseS2.json; cp model/results/idiom/gate.md model/results/idiom/gate_baseS2.md
say "gate: $?"
say "done"
