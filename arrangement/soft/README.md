# Soft tier: PROVISIONAL

The soft tier gives playing **costs, not violations**. Every threshold is a placeholder
(UNSOURCED.md S1-S9) and is waiting for the performer study to calibrate it. Each cost type is
reported on its own. Soft cost never enters playability or any aggregate score, and cost
types are never added together.

## Cost types and where they apply

| Cost type | Applies to (config block present) | Event, and its cost |
|---|---|---|
| breath | flute | A phrase (notes joined by gaps < `min_breath_gap`) longer than `max_phrase_seconds`. Cost = the seconds over. |
| bow | violin, viola, cello | A single note longer than `max_bow_seconds`. Cost = the seconds over. |
| shift | violin, viola, cello | A top-line interval > `frame_semitones` within `max_shift_ioi`. Cost = the semitones beyond the frame. |
| crossing | violin, viola, cello | A top-line string change. Cost = strings skipped + 1 if faster than `fast_ioi`. |
| register | violin, viola, cello, flute | A note above `comfortable_high`. Cost = the semitones above. |
| key | transposing instruments only (`transposition` ≠ 0; none in the real config) | A written note on a black key. Cost = 1. |
| repeated | all five instruments | A same-pitch repetition with IOI < `min_ioi`. Cost = (min_ioi − IOI) / min_ioi. |

Conventions:
- Grace notes are ignored.
- Times are in quarter notes. `_seconds` thresholds are converted at `assumed_qpm`.
- "Top line" = the highest note at each onset of the part.

Output per cost type (`soft_cost`): `__applies`, `__cost`, `__events`, `__per_100` (cost per
100 notes of the parts it applies to) and `__per_part`. Every output also carries
`soft_version` and `config_sha1`.

## Changing a threshold and re-running

Edit one number in `arrangement/config/soft.yaml`, or copy the file and edit the copy. Then:

    python -m arrangement.soft RECORDS.jsonl --config my_soft.yaml --out results/soft_try

This recomputes only the soft section and writes `soft.jsonl` and `soft.csv`, keyed by
`record_id` and tagged with the config hash. From Python, `soft_cost(score, ens, config=dict)`
takes an edited dict directly (`load_config()` returns the default as a dict).
