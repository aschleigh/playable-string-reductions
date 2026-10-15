**⚠ This analysis reasons about FABRICATED mock figures. No result exists yet.**

# Can the planned experiments tell the four outcomes apart?

The planned measurements are:
- **Playability:** hard-tier violations per 100 notes, per check type (D = the worst check type).
- **Fidelity:** Note F1, Note_i F1, Mel F1, I-IoU and harmonic agreement.
- **Texture and diversity detectors.**
- **Three tightness levels:** trio, duo, solo violin.
- **Possibly a performer study.**

The four outcomes:
1. Blocking matches training.
2. Training beats blocking at the same playability.
3. Training beats blocking, and blocking degrades as constraints tighten.
4. Neither improves on the unconstrained model.

**Short answer: no, not as planned.** Two of the six pairs can't be separated by the primary figure.
- **Outcome 2 vs outcome 3** can't be told apart at a single tightness level.
- **Outcome 1** ("matches on fidelity *and quality*") can't be confirmed by any planned measurement except the performer or listener study.

Three more pairs are separable only with additions that aren't yet in the plan:
- an equivalence test;
- a within-ensemble tightness axis;
- a way to compare at matched playability when the trained model doesn't reach exactly 0.

These are listed at the end.

## Pair by pair

| Pair | Separated by the primary figure? | What separates them |
|---|---|---|
| 1 vs 2 | Only if the gap is larger than the CI | A paired difference in fidelity at matched playability, plus a **pre-registered equivalence margin** for outcome 1 |
| 1 vs 3 | Only if outcome 3 already has a gap at the baseline | The tightness series (see 2 vs 3) |
| 1 vs 4 | Yes, *if* the unconstrained model has room to improve on x and the rule-based point is drawn | The rule-based reference point, plus the unconstrained-to-rule-based fidelity span |
| 2 vs 3 | **No.** At one level they look the same (compare the outcome 2 and outcome 3 mocks) | Tightness, ideally a **within-ensemble** knob, and fidelity normalised per level |
| 2 vs 4 | Yes | Trained model above blocking at x ≈ 0, versus both at the rule-based level |
| 3 vs 4 | Yes at the baseline | As 2 vs 4 |

### 1 vs 4: does the x axis leave room to improve?
Outcome 1 is "both are good"; outcome 4 is "both are no better than doing nothing smart". They separate only if the unconstrained model sits clearly to the right of 0 and the rule-based assigner sits clearly below it in fidelity.
- **The baseline has room.** Ou et al. on the trio has D = 5.12 [4.65, 5.59] (HEADROOM.md). Those violations are mostly chord_size (5.1) and range (4.2), and the range ones are almost all *below* the instrument's bottom note.
- **The string hard tier barely tells good writing from bad.** The floor is 0.0057 and naive is 0.56 per 100 notes (results/validation/README.md; NOTES.md). A system can reach x ≈ 0 by fixing over-full chords and octave errors while still writing unidiomatic parts. The checker sees no difference between outcome 1 and outcome 4 *beyond those two failure types*.
- **Separating them requires** the rule-based continuity point on every plot (fidelity of a cheap system that is already playable), and a ratio for each method's fidelity at x ≈ 0:
  > (F1 − F1_rule) / (F1_unconstrained − F1_rule)
  
  A ratio near 1 means outcome 1; near 0 means outcome 4. If the unconstrained model were itself near 0 on x (as AMT is, at 0.09), every method would collapse onto one point and the experiment couldn't tell any outcome apart. **So the trained and constrained systems must start from a base model with real headroom, like Ou et al. at D about 5, not from a model like AMT.**
- **The unconstrained point has to be the same base model the trained curve starts from**, the w = 0 end of the sweep. If it's Ou et al. while the curve comes from our own model, the mock's assumption that the curve starts at the unconstrained point doesn't hold, and outcome 4 ("no improvement on unconstrained") isn't defined.

### 1 vs 2: overlapping CIs
- **"Blocking matches training" is a claim of equivalence.** A non-significant difference doesn't establish it. It needs:
  - a margin fixed in advance, e.g. |ΔNote_i F1| < 0.02;
  - a paired equivalence test (two one-sided tests, or a 90% paired CI inside ±margin);
  - the same 150 inputs for both methods.
- **"Training beats blocking"** needs the paired 95% CI of the difference to sit entirely above 0, and above the margin to be worth claiming.
- **Paired resampling is essential.** The per-movement difference has much lower variance than either method's own spread across movements. The standard error is SD_diff / √150, so estimate SD_diff from the first real run before fixing N.
  - If the true gap is smaller than the margin, the result is outcome 1 by definition.
  - If the paired CI straddles the margin, the result is **inconclusive**. That's a fifth possible result and should be reported as one, as DECISION.md does with "Undecided".
- **Quality isn't on the plot.** Every fidelity metric measures *similarity to a reference* (Ou et al. App. C), not quality. Outcome 1's "and quality" half needs the listener or performer study. Without it, only "matches on fidelity" can be claimed.

### 2 vs 3: needs the tightness axis, and a common scale
- **At the baseline the two figures are the same by construction.** Only the tightness series separates them: the gap widens in outcome 3 (mock: +0.10 → +0.15 → +0.21) and stays flat in outcome 2.
- **Three tightness levels are the bare minimum for a trend.** With one level per ensemble, a "trend" is three points with no replication within a level.
- **The planned levels change the ensemble, not only the tightness.** Trio → duo → solo violin changes:
  - the number of parts;
  - the instrument-match term in Note_i F1;
  - the reference itself.

  So F1 isn't on a common scale across levels: everyone's fidelity falls at solo violin simply because one part can't carry four.
- **The solo regimes are close to infeasible for every system.** On solo violin naive scores 16.5 versus Ou et al.'s 16.1; on solo flute simultaneity is 185 versus 250 (HEADROOM.md). Blocking has to delete or transpose a large share of notes, so the low fidelity at those levels is largely the task's fault, not blocking's.
- **Implications:**
  1. **Compare gaps within each level, not absolute levels.** Report blocking's fidelity as a fraction of the unconstrained model's fidelity at that level, or as the normalised ratio from 1 vs 4.
  2. **"Blocking degrades" means that fraction falls with tightness while the trained model's doesn't.** Test it as a slope across levels, with a paired bootstrap.
  3. **Add a within-ensemble tightness knob (recommended).** Keep the trio and its reference fixed, and tighten the thresholds:
     - range narrowed by k semitones from the top;
     - `max_chord` 4 → 3 → 2;
     - transition cap reduced.

     This varies tightness while holding the reference fixed. It's the only design where "the gap widens with tightness" isn't confounded with "the ensemble changed". Keep the cross-ensemble series as the second, practical axis.

### The zero-violation end
- **Blocking sits at exactly 0 by construction**, but only with the per-commit mask on every check, and transition is non-monotone (NOTES.md). If blocking masks only the monotone checks, it won't be at exactly 0 on transition either. Report that check separately.
- **The trained model isn't expected to reach exactly 0.** A soft reward with sampled decoding leaves a residual, and the mock puts it at about 0.1. "At the same playability" then has no matching point on the trained curve. Options, best first:
  1. **Compare at a matched rate, and say so.** For example, "at r ≤ 0.1, the trained model's fidelity is X; blocking reaches r = 0 at fidelity Y". The plot shows blocking dominating on playability. Whether the residual 0.1 matters is a separate question (soft tier, performer study). Don't extrapolate the curve to 0.
  2. **Add a trained + blocking point:** the trained model decoded under the mask. It's cheap, sits at exactly 0, and directly answers "does training help at zero violations?" **This is the most useful missing measurement.**
  3. Zero-violation subset (fidelity on the movements where the trained model happened to hit 0). This is biased toward easy movements, so report it only alongside the same subset for blocking.
- **D's worst check can change along the curve.** The x axis can hide the trained model trading chord-size violations for range violations, so draw the per-check-type version of the figure next to the D version.

### Reward hacking: the plot can't tell "better" from "gamed"
A trained point that moves up and to the left could be genuinely better, or it could be gaming the checker or the reward. The primary figure can't separate the two. Every trained sweep point needs its texture and diversity detectors reported next to it:
- **Note count per part versus the source.** Sparsity lowers the violation rate; Note_i F1 penalises it only through recall.
- **Doubling rate.**
- **Polyphony rate.**
- **Mean duration versus the source.** Long held notes reduce transition violations.
- **Seed variance.**
- **Near-limit distribution:** for example, leaps piling up just under the transition cap, or chords sitting at exactly `max_chord`. This is the direct signature of the model learning the checker rather than the instrument.
- **Harmonic agreement.** This is the reward's own target, so on that metric the trained model is graded on what it was trained for. Read gains there as the least trustworthy.

**Rule to fix in advance:** a trained point counts toward outcome 2 or 3 only if each detector stays within the range spanned by the unconstrained model and the rule-based assigner. The range should be fixed before training.

## Measurements to add to the plan

1. **The rule-based continuity point on every playability–fidelity plot**, plus the normalised fidelity ratio. *Separates 1 from 4.*
2. **Paired bootstrap of fidelity differences**, with a pre-registered equivalence margin. *Separates 1 from 2, and makes "inconclusive" an explicit result.*
3. **A within-ensemble tightness knob** (trio with tightened thresholds), alongside the cross-ensemble series. Fidelity normalised per level. *Separates 2 from 3, and 1 from a version of 3 with no gap at the baseline.*
4. **A trained + blocking point.** *Settles "at the same playability" when the trained curve stops short of 0.*
5. **Detector values attached to every plotted point**, with a rule fixed in advance. *Separates "better" from "gamed".*
6. **The performer or listener study.** *The only measurement of outcome 1's "quality" half, and of whether hard-tier x ≈ 0 means playable to a performer.*

**The base model's headroom decides whether any of this can work.** If the unconstrained point isn't clearly to the right of 0 (the AMT case), all four outcomes look the same.
