# Block 3 → Block 4 handoff

**Project:** a thesis on RL for playable music arrangement.
- Repo: `/scratch/ashleyz/reduction_ladder`, branch `headroom`.
- Block 3 (the model block) is finished. Block 4 is RL with the reward, run on the masked model.
- Full write-ups: MODEL.md (the model), DECODING.md (the gate and baselines), REVIEW.md
  R23–R27 (decisions), METRICS.md (metrics), UNSOURCED.md (placeholder thresholds).

## 1. What exists at the end of Block 3

**Hard-tier checker, frozen at tag `checker-v4`.** It was revised three times after
MuseScore review by the user (a string player).
- Checks: simultaneity, range, chord_size, hand_span, transition, multistop, bow, shift,
  duplicate, hand_leap, triple_onset, triple_stretch, triple_rate, double_onset, restrike,
  double_rate.
- It has three equivalent interfaces: batch `check`, `IncrementalChecker`, and `GrowingChecker`
  (`would_add`/`add`, used for masking).
- Thresholds U14–U18 (triple-stop width, triple-stop rate, double-stop rate) are placeholders.
- Repeating the same double stop is exempt from double_rate.
- **Known imperfection:** real source quartets also trigger some v4 checks. The Bridge
  excerpt has 8 such notes in 16 bars.

**Metrics harness, METRICS 1.3.0-draft.**
- **D:** the worst single check per 100 notes, with a 95% movement-bootstrap CI.
- **Fidelity vs the source:** Note_i F1 (note plus instrument), Note F1, Mel F1
  (highest-mean-pitch part), Mel-top F1 (top voice across all parts), harmony (chroma per beat).
- **Texture:** polyphony rate, rhythmic independence, doubling rate, note ratio.
- **Rule from Block 2:** the checker and metrics are never changed quietly. They are
  versioned, and the baselines are re-run.

**The arranger model, `arranger-v1`.**
- Checkpoint: `model/results/arranger-v1/checkpoint.pt` (gitignored).
- 4.94M-parameter transformer encoder (d256, 6 layers), trained from scratch with no pretraining.
- Input: the source notes plus part tokens. Three heads per note:
  - part: dot product with the part tokens, plus DROP;
  - octave: −24 to +24;
  - realisation: plain, tremolo, repeat, arpeggiate, or *double* (octave double stop).
- `model/augment.py::expand()` turns the labels into output notes.
- **Training:** supervised only, on 476 OpenScore quartet movements, with the 150 evaluation
  movements excluded.
  - Targets are the true parts merged into trio (Vn1+Vn2 → violin) or duo
    (Vn1+Vn2 → violin, Va+Vc → cello).
  - Realisation labels come from collapsing real figuration.
  - Two phases: supervised recovery, then partially committed states (reveal up to 90%).
  - 30k steps, 47 minutes on one RTX 6000 Ada.
  - Equal head losses with unweighted classes.
- **Validation:** part accuracy 0.85, octave 0.97. Realisation recall: arpeggiate 0.86,
  repeat 0.49, tremolo 0.35, double 0.02.
- **Decoding (`model/decode.py`):** 16-quarter windows with 8 quarters of committed context.
  Each pass commits the most confident half of the undecided notes.
  - **Masked:** each note takes its most probable joint option (part × octave × realisation)
    that adds no hard violation, via GrowingChecker. DROP is always feasible, so D = 0 by
    construction.
  - A masked decode of 150 movements takes about 7 minutes on 6 GPU shards.

**Reference systems** (records in `headroom/data/records/`):
- Ou et al. unconstrained, masked under v4, and Ou + repair (deterministic re-routing);
- continuity (copy) and naive;
- AMT (secondary, 32 bars, copy-diluted).

**Gate (DECODING.md, pre-registered).** Under v4 every string regime gives **outcome 2/3**:
masking costs Ou et al. fidelity, so learning has a target. Ou's cost from masking:

| Regime | Note_i F1 | Harmony |
|---|---|---|
| trio | 0.086 | 0.092 |
| duo | 0.119 | 0.148 |
| solo violin | 0.148 | 0.265 |
| solo flute | n/a | 0.297 |

The piano gate is finishing.

## 2. Results at the end of Block 3

150 evaluation movements per regime; checker-v4; METRICS 1.3.0-draft.

| System | D trio / duo | Note_i F1 trio / duo | Harmony trio / duo | Mel-top F1 trio / duo |
|---|---|---|---|---|
| **arranger, masked** | **0 / 0** | **0.741 / 0.608** | 0.982 / 0.928 | 0.924 / 0.832 |
| arranger, unmasked | 12.2 / 20.6 | 0.871 / 0.707 | 0.999 / 0.999 | 0.987 / 0.984 |
| Ou et al., masked | ≈0 / 0 | 0.412 / 0.387 | 0.712 / 0.684 | 0.635 / 0.630 |
| Ou et al. + repair | 0 / 0 | 0.390 / 0.372 | 0.758 / 0.741 | 0.703 / 0.679 |
| continuity | 10.2 / 20.6 | 0.678 / 0.682 | 1.000 / 1.000 | 1.000 / 1.000 |

**Findings:**
- **The masked arranger is the only system that is both playable and close to the source.**
  It beats both playable Ou et al. variants by +0.2 to +0.35 Note_i F1, with all CIs clear of zero.
- **The duo is weak.** It loses to continuity on every fidelity metric, because masking drops
  19% of notes there.
- **The model has not learnt playability.** Unmasked, its D is about continuity's. In the
  masked duo the top choice is infeasible for 22% of notes (12% in the trio; corrected
  2026-10-12, an earlier version said 51% / 24% from a counter of failed options), so the mask
  does the playability work. **This is the gap Block 4 targets.**
- **Too many double stops.** The user's review of the Bridge excerpt (bars 60–75) found too
  many double stops in the masked violin part. They come mostly from merging Vn1 and Vn2.
  The double stops are legal under the checker but hard to play.

**Caveats for any write-up:**
- Fidelity vs the source favours copy and re-assignment systems over generative ones (R21).
- Mel F1 penalises the merged violin part, so Mel-top F1 is reported alongside it.

## 3. Decisions the user has made for Block 4

1. **Keep the mask** during RL and at evaluation. The hard tier stays a constraint, not a reward term.
2. **Dropping a note is much better than a hard-to-play passage.**
3. **Penalise double stops that the source does not have**, in the final arrangement. They
   are hard for string players and impossible for winds.
   - Prefer dropping an unnecessary or less important note of the double stop, or dropping
     a less important inner voice, over keeping a hard double stop.
   - This implies an **importance-weighted fidelity term**: melody (top voice) and bass are
     protected, and inner voices are cheaper to drop.
4. **Regimes: trio and duo.** The user asked why solo was stopped; whether to add solo
   violin and solo flute is open (Q2).
5. **The checker is still imperfect,** so the reward should not assume the checker is the
   whole story of playability.
6. **"Follow all recommendations":**
   - **Retrain as `arranger-v2`** with class weighting on repeat, tremolo and arpeggiate,
     but **not** on *double*: weighting double up would contradict decision 3.
     arranger-v2 becomes the RL starting point.
   - **Keep U14–U18 as placeholders** unless the user's excerpt review changes them.
   - **Delete the stale debug records** (`model/results/arranger-v1/records_broken_run1/`, `records_old_expand/`).
7. **Do not start until the Block 4 brief is approved.**

## 4. Open questions for the Block 4 brief

- **Q1. Compute ceiling.**
  - Available: two shared RTX 6000 Ada GPUs, 48 GB each. Other users hold about 35–44 GB,
    so in practice there is about 13 GB on GPU 1.
  - Also 64 CPU cores and about 250 GB of RAM.
  - Rough estimate: an RL run takes a few hours to a day on one GPU.
  - Proposed default: at most one GPU and 24 hours per run.
- **Q2. Solo regimes.** Add solo violin and solo flute?
  - Adding them is cheap: new target ensembles in augment.py.
  - Flute would use plain notes only.
  - Solo violin is where the double-stop penalty matters most.
  - Piano stays out, because the model has no keyboard texture ops.
- **Q3. Reward composition and weights.** For example:
  - importance-weighted fidelity (melody, bass, inner voices);
  - an unneeded double-stop penalty (two or more sounding notes in one output part that
    came from different source parts or were not a double stop in the source);
  - harmony, and possibly texture closeness to the source.
  How each term is defined and weighted is a research decision for the user.
- **Q4. Algorithm details:**
  - GRPO group size, and the unit of a sample (window or movement);
  - whether the mask is applied inside sampling (yes, per decision 1) and how the policy
    ratio treats masked-out options;
  - a KL anchor to arranger-v2;
  - which split to train RL on (the train split only, never the 150 evaluation movements).
- **Q5. Evaluation and success criterion.**
  - The same harness and baselines, plus new reported metrics: the unneeded double-stop
    rate, and importance-weighted fidelity reported per tier.
  - The new metrics need a METRICS version bump and baseline re-runs.
  - Possible success criterion: beat masked arranger-v2 on importance-weighted fidelity at
    a lower double-stop rate. Pre-register it, as the gate was.
- **Q6. User review.** Which excerpts the user reviews in MuseScore, and when.
  - Renderer: `decoding/render_excerpts.py --model-run <run>`.
  - Current excerpts: `decoding/results/examples/arranger-v1/`.

## 5. Guardrails carried over

- **Never change the checker or METRICS quietly.** Version them and re-run the baselines.
- **Research-consequence decisions are the user's:** reward terms, weights, thresholds,
  and transforms.
- **AMT is included in every experiment** as secondary, with the copy-dilution caveat.
- **Evaluation movements are never used for training or tuning.**
- **Stop and report at each step boundary.** When the user delegates while away, log the
  decisions in REVIEW.md.
- **If a pretrained backbone seems required, stop and say so.**
