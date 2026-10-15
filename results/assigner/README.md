# Assigner tuning and held-out accuracy

Metric: note-level label accuracy against the score's real parts (Vn1, Vn2, Va, Vc).
The checker is never consulted. Dev split = movements with `crc32(key) % 10 == 0`
(61 movements, 206,686 notes). Held out = the other 626 movements (2,190,888 notes).

| Assigner | Dev | Held out |
|---|---|---|
| naive (pitch bands) | 0.288 | 0.295 |
| continuity, crossing allowed (w_cont 0, w_busy 64) | 0.631 | 0.649 |
| **continuity, no crossing within a slice (configured: w_cont 16, w_busy 1024)** | **0.742** | **0.753** |

Updated 2026-10-06 after the parser fixes and calibrated upper ranges. Naive's bands come from the configured
instrument ranges, so the new upper bounds moved them (naive held-out accuracy was 0.335 before). The
continuity optimum did not move.

Findings that shaped the baseline:
1. With unconstrained per-slice matching (the originally approved decision 6), the best
   continuity weight is **0**: pitch proximity to the part's previous note *lowers* accuracy.
   All of the gain over naive comes from the busy/spreading term. That would not be a
   continuity baseline.
2. Forbidding part crossing inside a slice (notes sorted by pitch are split into contiguous
   blocks in band order) makes the continuity term useful. Accuracy rises with w_cont up to
   16 (the optimum lies inside the grid).
3. Crossing-allowed matching is fragile under ties. Feeding the slice's notes to the matcher
   in descending instead of ascending pitch order drops dev accuracy from 0.642 to 0.535,
   with the same costs. The configured no-crossing mode has no such dependence on the
   matcher's row order.
4. w_busy has a plateau from 1024 up, so the busy term acts lexicographically: spread notes
   across free parts first, then use band + continuity.

Files: `tuning.json` (full grid), `heldout_accuracy.json`. Reproduce with
`python -m arrangement.tune_assigner` and `python -m arrangement.tune_assigner --heldout`.
