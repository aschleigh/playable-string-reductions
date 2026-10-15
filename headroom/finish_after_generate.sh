#!/usr/bin/env bash
# Wait for headroom/generate.sh, re-run it with fewer workers to fill shards
# that failed (e.g. CUDA OOM on the shared GPUs; existing outputs are skipped),
# then measure + figure + report + archive.
cd "$(dirname "$0")/.."
wait_gen() { while pgrep -f "headroom/generate.sh" > /dev/null; do sleep 60; done; }
count() { ls headroom/data/out/*/*/*.json 2>/dev/null | wc -l; }
wait_gen
for attempt in 1 2 3; do
  [ "$(count)" -ge 900 ] && break
  echo "$(date) fill pass $attempt: $(count)/900 present" >> headroom/data/finish.log
  headroom/generate.sh 3 3
  wait_gen
done
CK=.venv/bin/python
{ date; echo "outputs present: $(count)/900"
  $CK -W ignore -m headroom.measure --workers 32 && $CK -m headroom.figure && $CK -m headroom.report \
    && tar -czf headroom/results/outputs.tar.gz -C headroom/data out eval_set.json
  echo "exit $?"; date; } >> headroom/data/finish.log 2>&1
