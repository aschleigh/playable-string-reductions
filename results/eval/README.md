# First harness run: the headroom sweep (METRICS 1.0.0-draft)

`headroom_sweep/` is `python -m arrangement.eval.harness headroom/data/records/*.jsonl`. The records
come from `python -m headroom.to_records`: 150 evaluation movements, every system and regime of
HEADROOM.md. `metrics.jsonl` is not tracked (18 MB; rebuild with the command above). `metrics.csv`
is the same content, flattened.

Pooled over movements. Playability = Σ violations / Σ notes × 100. Fidelity = Σ segment values /
Σ segments, against the **source** (§5.3). There is no human reference except the quartet floor.

| system | ensemble | range | chord | trans. | simult. | h-span | Note F1 | Note_i F1 | Mel F1 | Mel-top F1* | I-IoU | Harmony* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| floor | quartet | 0.00 | 0.00 | 0.01 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| naive | quartet | 0.00 | 0.64 | 0.00 | 0 | 0 | 1.000 | 0.431 | 0.714 | 1.000 | 0.788 | 1.000 |
| continuity | quartet | 0.33 | 0.00 | 0.01 | 0 | 0 | 1.000 | 0.849 | 0.910 | 1.000 | 0.955 | 1.000 |
| control | quartet | 10.36 | 0.09 | 1.34 | 0 | 0 | 1.000 | 0.400 | 0.460 | 1.000 | 0.887 | 1.000 |
| **ou_band** | **trio** | 4.18 | 5.12 | 0.23 | 0 | 0 | 0.672 | 0.498 | 0.586 | 0.785 | 0.879 | 0.804 |
| amt | trio | 0.09 | 0.02 | 0.01 | 0 | 0 | 0.463 | 0.434 | 0.859 | 0.803 | 0.838 | 0.660 |
| naive | trio | 0.00 | 0.65 | 0.00 | 0 | 0 | 1.000 | 0.431 | 0.724 | 1.000 | 0.788 | 1.000 |
| continuity | trio | 0.15 | 0.01 | 0.04 | 0 | 0 | 1.000 | 0.678 | 0.853 | 1.000 | 0.937 | 1.000 |
| control | trio | 8.30 | 0.23 | 1.34 | 0 | 0 | 1.000 | 0.343 | 0.465 | 1.000 | 0.893 | 1.000 |
| ou_band | duo | 7.82 | 8.18 | 0.42 | 0 | 0 | 0.749 | 0.506 | 0.511 | 0.825 | 0.601 | 0.832 |
| naive | duo | 0.00 | 1.43 | 0.03 | 0 | 0 | 1.000 | 0.511 | 0.707 | 1.000 | 0.598 | 1.000 |
| continuity | duo | 0.38 | 0.09 | 0.07 | 0 | 0 | 1.000 | 0.682 | 0.703 | 1.000 | 0.648 | 1.000 |
| ou_band | solo_violin | 16.09 | 11.30 | 0.40 | 0 | 0 | 0.903 | 0.522 | 0.475 | 0.862 | 0.377 | 0.861 |
| naive | solo_violin | 16.50 | 5.70 | 0.07 | 0 | 0 | 1.000 | 0.561 | 0.480 | 1.000 | 0.380 | 1.000 |
| ou_band | solo_flute | 28.68 | 0 | 0 | 250.0 | 0 | 0.795 | 0.000 | 0.422 | 0.755 | 0.000 | 0.767 |
| naive | solo_flute | 29.97 | 0 | 0 | 185.1 | 0 | 1.000 | 0.000 | 0.480 | 1.000 | 0.000 | 1.000 |
| ou_piano | piano | 0.43 | 0.54 | 0 | 0 | 1.42 | 0.290 | 0.000 | 0.143 | 0.225 | 0.000 | 0.587 |
| naive | piano | 0.00 | 0.02 | 0 | 0 | 5.64 | 1.000 | 0.000 | 0.480 | 1.000 | 0.000 | 1.000 |

\* our additions (METRICS.md §5.5). Single-part regimes: control = naive (all notes in one part).

**Cross-check.** Every playability number equals HEADROOM.md, which came from an independent code
path (`headroom/measure.py`).

## What the first run shows about the metrics themselves

1. **Against the source, Note F1, top-voice melody F1 and harmony are 1 by construction for every
   system that places source notes and drops none:** naive, continuity, the control, and any
   constrained decoder or trained policy that only assigns. For those systems, only Note_i F1,
   Mel F1 and I-IoU move. The reward-relevant consequence: **harmonic agreement cannot be a
   training signal for a pure assignment policy,** because it is constant. It becomes informative
   only once the system may drop, add or re-pitch notes. That is necessarily the case in the solo
   regimes, and optional in trio and duo. → REVIEW.md R21.
2. **Note_i F1 and I-IoU are 0 by construction where the target instrument is absent from the
   source** (flute, piano), as published (R5). In those regimes the fidelity axis of the primary
   figure has to use Note F1, Mel F1 or harmony.
3. **Mel F1 (paper) and top-voice melody F1 (addition) disagree substantially for Ou et al.**
   (trio 0.586 vs 0.785). The highest-mean-pitch track often isn't where the melody sits. That is
   worth reporting next to the published metric.
4. **AMT's high Mel F1 (0.859) comes from the copied Violin 1 control line;** its Note F1 is the
   lowest (0.463), because it writes new viola and cello parts.
