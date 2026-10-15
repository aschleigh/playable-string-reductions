#!/usr/bin/env bash
# Detached: wait for the R46 confirmatory evaluation, then build the week-summary table and figure.
cd "$(dirname "$0")/.."
LOG=model/logs/rl_chain.log
until grep -q "\[confirm\] evaluated" "$LOG"; do sleep 60; done
CUDA_VISIBLE_DEVICES="" .venv/bin/python -W ignore -m model.week_summary > model/logs/week_summary.log 2>&1
echo "$(date '+%F %T') [summary] table + figure built: $?" >> "$LOG"
