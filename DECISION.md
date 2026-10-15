# Decision rule for the headroom measurement (pre-registered)

Written 2026-10-06, **before any system output was generated or checked**. It is
committed together with the frozen checker (git tag `checker-v1`), so the commit
date shows that the rule came before the result. The interpretation below may not
be changed after results exist. Any change gets a dated amendment at the bottom,
with the reason, and the original text stays.

## What is measured

A **system** arranges a **source** for a **target ensemble** (the pairing is in
HEADROOM.md). Its output is checked by the frozen hard-tier checker (tag
`checker-v1`; `arrangement/checker`, `arrangement/config`) under one
**constraint regime**: an ensemble with its instrument definitions.

For each system and regime, and each check type c (simultaneity, range, chord_size,
hand_span, transition):

- r_c = violations of type c per 100 notes **in the system's output**, pooled over
  all evaluation scores (`checker.report.rates_per_100`, `violations_per_100`).
  Check types are never summed.

**Decision statistic: D = max over c of r_c, reported with the check type that
attains it.** This is the worst single check type, not a sum. It is used because
the binding constraint depends on the regime (chord size for strings, hand span
for keyboard, simultaneity for monophonic instruments). A fixed check type would
read 0 by construction in some regimes. Every r_c is reported alongside D.

**Interval:** 95% percentile bootstrap over scores (resample scores with
replacement, recompute every pooled r_c, take the max; 10,000 resamples, seed 0).
Bootstrapping D itself accounts for picking the maximum.

## Decision thresholds (on the baseline regime: string quartet)

| Bootstrap 95% CI of D | Decision |
|---|---|
| entirely above 5 | **Proceed**: clear headroom; the project goes ahead as planned. |
| entirely within [1, 5] | **Tighten**: headroom exists but the effect will be small. Use the sweep (solo instruments, keyboard with hand spans, unusual ensembles) to find a regime where it matters. |
| entirely below 1 | **Pivot** to difficulty-controlled arrangement, subject to the validity conditions below. |
| spans 1 or 5 | **Undecided**: the measurement does not decide. Reported as such, with no point-estimate verdict. |

The baseline regime decides. The tightening sweep is reported as a curve of D
(and each r_c) against constraint tightness. It does not override the baseline
decision. A sweep regime with a valid control and a CI entirely above 5 is
reported as a secondary finding, and in the "Tighten" branch it names the regime
to pursue.

## Validity conditions (all must hold for a decision to count)

1. **Positive control.** For each regime, the same evaluation inputs are
   arranged by a known-unplayable control: **random part assignment**, where each
   source note goes to a part chosen uniformly at random (seed 0), keeping pitch
   and timing. If the control's D CI is not entirely above 5 in a regime, the
   checker cannot register headroom there. A low system rate in that regime is
   then reported as **"uninformative: checker insensitive"**, never as "Pivot".
   For the baseline, this means Pivot needs the quartet control to pass.
2. **Sparsity guard.** Output notes are compared with source notes, per part
   and in total. If a system's total output has fewer than **80%** of the source
   notes, its rate counts as **sparsity, not playability**. The report leads with
   that, and the system cannot trigger "Pivot". Per-part counts are always
   reported.
3. **Floor reference.** Wherever published human scores exist for a regime, their
   D and r_c (checked by the same frozen checker) are reported next to the
   system's. The quartet floor from `results/validation` is D = 0.0057 per 100
   notes (transition). Its thresholds were calibrated on that same corpus, so the
   floor passes partly by construction (UNSOURCED.md).
4. **System class.** The decision applies only to the class of system measured.
   If no neural arrangement system runs and the rule-based assigner carries the
   measurement, every result is labelled **"headroom against rule-based
   systems"**. It is not evidence about neural arrangement, and HEADROOM.md says
   so at the top.
5. **Frozen checker.** Every number comes from tag `checker-v1`. A checker or
   config bug found while measuring is reported and not fixed mid-measurement.
   A fix means a new tag and a full re-run, with both results kept.

## Second reading of a low number

If a model trained on real scores produces playable output without being told
to (D below 1 with a valid control and no sparsity), it has absorbed the physical
constraints from data alone. That is a finding in itself, not only a negative
result, and HEADROOM.md reports it as such. It still triggers the Pivot branch.

## Amendments

### A1 (2026-10-06, before any evaluation output existed)

Decided with the user after Step 2 showed what runs. Three test arrangements of
one movement were generated to test the pipeline. They were deleted unchecked
before this amendment was committed, and every evaluation output is generated
after it.

1. **Baseline regime = string trio (Vn/Va/Vc)**, not string quartet. Reason:
   the primary system cannot emit a quartet. REMI-z keeps one track per GM
   program, so two violins collapse into one track. The trio is that system's own
   preset. The 1/5 thresholds and every validity condition above apply to the
   trio. The quartet is still measured (rule-based systems, true-part floor,
   control).
2. **Systems.**
   - *Primary (drives the decision):* Ou et al., NeurIPS 2025, released weights
     `LongshenOu/m2m_arranger` (band) and `LongshenOu/m2m_pianist_dur` (piano
     regime). Prompt and sampling are as in the released `api/arranger.py`.
     History = previous output bar, as in the paper's `m2m/reinst.py`
     (`hist_autoregressive: True`); the released API leaves it empty. One sample
     per (movement, regime), seed = crc32(key|system|regime). Nothing else is
     changed.
   - *Secondary (reported, never decides):* Anticipatory Music Transformer
     (`stanford-crfm/music-medium-800k`) in accompaniment mode: the source's
     Violin 1 is the control, the first 2 bars are the prompt, generation runs
     to the end of bar 32. Trio regime only. It is generation, not arrangement.
   - *Rule-based (reported, labelled "rule-based"):* naive and continuity
     assigners from the frozen code, every regime.
3. **Evaluation set:** 150 movements, a seeded random sample (seed 0) of the 626
   non-dev OpenScore quartet movements. None was used for assigner tuning or
   transition calibration. Upper ranges were fitted on the full corpus, so
   source pitches are inside the string ranges by construction, and any range
   violation is the system's doing. Source = all four parts; the system arranges
   the quartet FOR the regime's ensemble (a reduction in every regime except
   piano). Grace notes are dropped for every system and control. Classical
   chamber input is out of distribution for both neural systems (trained on Lakh
   MIDI). That limits the claim to "these systems on classical quartet sources".
4. **Regimes (checker-v1.1: checker code identical to v1; the config adds
   flute, piano and the ensembles):** quartet, trio (baseline), Vn+Vc duo, solo
   violin, solo flute (monophonic; transition off), solo piano (hand span
   placeholder U8; transition off). Tightness axis: quartet → trio → duo → solo
   violin → solo flute. Piano is a separate keyboard point.
5. **Positive control:** random assignment of the source notes to the regime's
   parts. In single-part regimes it is all source notes in the one part, i.e.
   no reduction.
6. **Sparsity guard, replaced.** The original rule (total output < 80% of source
   notes) assumed a target the size of the source; for a reduction it flags
   every faithful reduction. It is replaced by **per-part retention**: output
   notes of a target part / notes of its reference source part (violin → Vn1,
   viola → Va, cello → Vc, flute → Vn1, piano → all four parts). A system is
   *sparse* if any target part's retention is below 0.8. Sparse systems cannot
   trigger Pivot. Total retention and the original rule's verdict are still
   reported.
7. **Off-ensemble notes** (output on a program outside the regime) are counted
   and reported, excluded from checking, and count against retention.
8. **Floor:** human scores exist only for the quartet regime (the true parts of
   the same 150 movements). Every other regime has no floor; it is reported as
   absent, not estimated.
