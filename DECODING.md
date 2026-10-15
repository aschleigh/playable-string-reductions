# Constrained decoding on Ou et al.: the gate (pre-registered)

Written 2026-10-08, **before any constrained output was generated.** It is committed before the run.
Any later change gets a dated amendment at the bottom, and the original text stays.

## Question

Does masking every token that would create a hard violation make Ou et al. playable at little
cost in fidelity? If it does, RL has little left to add (outcome 1).

## What is run

- **System:** Ou et al. band arranger, the same weights, prompt, sampling settings, history rule and
  per-movement seed as the unconstrained headroom run (DECISION.md A1.2). The only change is a
  logits processor:
  - Before a pitch token, every pitch whose note would add a hard violation to the notes already
    generated in that part is set to −∞. The note is placed at the current instrument and position,
    and its length is irrelevant there: chord size at its own onset, transition and range do not
    depend on its own duration.
  - Before a duration token, durations that would add a violation are also masked. This applies only
    when the note could overlap notes already committed later in time in the same part (notes
    spilling past a bar line), or when the position changed after the pitch was chosen.
  - The decision uses the frozen checker's own rule code: `arrangement/decode/growing.py`, a subclass
    of `IncrementalChecker` that only adds note storage. It is tested equal to the batch checker.
  - Instruments outside the target ensemble are not masked: they are dropped by the harness, exactly
    as in the unconstrained run.
- **Regime:** string trio (the decision baseline, DECISION.md A1.1), 150 evaluation movements. The
  Vn + Vc duo is run as a secondary result if time allows; it does not decide.
- **Scoring:** the frozen harness (METRICS.md 1.0.0-draft, git tag `metrics-1.0.0-draft`, unchanged),
  with fidelity measured against the source (§5.3).
- **References in every table:** unconstrained Ou et al. (same seeds), the continuity assigner, and
  unconstrained AMT (secondary, 32-bar window).

## Statistics

Everything is pooled over movements, with a 95% percentile bootstrap over movements (10,000
resamples, seed 0).
- **Playability:** D = the worst single check type, violations per 100 notes, as in DECISION.md.
- **Fidelity loss:** paired Δ_m = unconstrained − constrained for each metric m ∈ {Note_i F1,
  Note F1, Mel F1, harmony}. Each value is pooled as Σ segment values / Σ segments (Σ beats for
  harmony). The bootstrap resamples movements jointly for both arms.
- **Primary fidelity metric:** Note_i F1, the paper's headline. Harmony is co-primary, because it is
  what the reward will optimise.
- **Margin: 0.02 absolute (2 points).** This is the smallest difference Ou et al. treat as a real
  effect: REMI-z over REMI+ is +1.9 Note_i F1, reported as significant.

## Decision rule

| Playability (D) | Fidelity loss (Note_i F1 and harmony) | Reading |
|---|---|---|
| D's CI upper bound ≤ 0.5 | Δ's CI upper bound < 0.02 for both Note_i F1 and harmony (Note F1 reported) | **Outcome 1.** Blocking is enough; RL has little to add. **Stop and talk before any model is built.** |
| D's CI upper bound ≤ 0.5 | Δ's CI lower bound > 0.02 for Note_i F1 or harmony | **Outcome 2 or 3.** Training has a clear target; the hypothesis is live. Proceed. |
| D's CI upper bound ≤ 0.5 | anything else (a CI straddles 0.02) | **Undecided on fidelity.** Outcome 1 is not established, so proceed, flagged in every report. |
| D's CI upper bound > 0.5 | — | **Blocking failed to reach low violations.** Diagnose (incomplete masking, or a constraint not expressible token by token) before proceeding. |

0.5 per 100 notes is half of DECISION.md's pivot threshold, and is about the level of the continuity
assigner (trio 0.17, duo 0.39). Sparsity is reported too: per-part and total note ratio against the
unconstrained run. A constrained run that reaches 0 violations by emitting far fewer notes shows up
there, and as a Note F1 recall loss.

## Amendments

### A1 (2026-10-08, before any checker-v2 masked output was generated): re-run under checker-v2

**Why.** The user inspected the masked trio in MuseScore (`decoding/results/examples/`) and found it
unplayable: for example a cello B2–G4–B4 chord, and many like it. Checker-v1 only caught surplus notes,
so it called that output clean. The user approved new hard rules (multistop, bow, shift, duplicate,
hand_leap). They are frozen as tag `checker-v2`, with METRICS 1.1.0-draft, and their floor validation
is in `results/validation_v2/`.

**The checker-v1 result above stands** as the result under checker-v1. It is not edited or
overwritten. Its masked outputs are archived in `headroom/data/out/ou_band_masked_checker-v1/`.

**What is re-run.** Same model, prompt, sampling, seeds and masking method. The only change is that
the masks now come from the checker-v2 rules. Duration tokens are now also masked on string parts,
because the bow rule depends on a note's own duration.
- **Trio (deciding):** the decision rule, margin (0.02), D threshold (0.5) and bootstrap are
  unchanged. D is the worst single check under checker-v2.
- **Secondary (reported, never deciding):** the rule is applied to each and its verdict reported.
  - duo (replacing the checker-v1 duo run, which was never written up);
  - solo_violin and solo_flute (masked Ou band arranger);
  - piano (masked Ou piano arranger `m2m_pianist_dur`, paired with `ou_piano`).
- **Baselines** for each regime are re-scored with checker-v2 and the 1.1.0-draft harness, with the
  same outputs: Ou unconstrained, continuity, naive, control, and AMT (trio only, secondary, 32-bar
  window, ~41% copied control line).
- The headroom measurement (`headroom.measure`, DECISION.md) is re-run under checker-v2 into
  `headroom/results_v2/` as a **descriptive** re-measurement. The formal DECISION.md verdict
  (Undecided, under checker-v1.1) is not re-decided by it.

**Known limits, stated in advance.**
- U12/U13 (piano hand leap) and U9 (violin/viola stretch) are placeholders.
- The shift rule fires on no corpus assignment, so it is untested as a discriminator (TRIAGE_V2.md).
- Greedy masking can only block the next token. If a context leaves no legal pitch, the model emits
  some other token, and `all_masked` counts the steps where every token was blocked.

Results go to `decoding/results/v2/<regime>/`.

### A2 (2026-10-09, before any checker-v3 masked output was generated): re-run under checker-v3

**Why.** The user inspected the checker-v2-masked trio (`067_bars1-16_checker-v2/3_…`) and found it
still unplayable:
- fast successions of triple stops (cello bar 13, violin bar 3);
- tightly packed violin chords.

The diagnosis:
- most of these "chords" are overlapping notes in fast runs, never struck together;
- the bow rule allowed three strings held for up to 2 beats;
- the 3+-note stretch equalled the double-stop stretch.

One violin "chord" in bar 3 was an artefact of the renderer's 16th rounding, which is now marked
blue in the MuseScore files.

The user approved three new rules plus a bow change, frozen as `checker-v3` with METRICS 1.2.0-draft;
the floor validation is in `results/validation_v3/`:
- triple_onset;
- triple_stretch (cello 4, violin/viola 5);
- triple_rate (1 quarter);
- bow d = 0.5.

**The checker-v1 and checker-v2 results above stand** under their own checkers. The v2 masked outputs
are archived as `headroom/data/out/*_masked_checker-v2/`.

**What is re-run.** Everything listed in A1, unchanged except that the masks come from checker-v3.
- The trio still decides, with the same rule, margin and D threshold.
- Duo, solo violin, solo flute and piano are secondary.
- Whether the deciding regime should move to the duo was raised with the user on 2026-10-08 and has
  not been decided. It is not changed here.

Results: `decoding/results/v3/<regime>/`; the headroom re-measurement: `headroom/results_v3/`.

### A3 (2026-10-12, before any checker-v4 masked output beyond the 5 review movements): checker-v4, plus a repair baseline

**Why.** The user reviewed the checker-v3-masked trio and found two problems, now frozen as tag
`checker-v4` (METRICS 1.3.0-draft; floor in `results/validation_v4/`):
- held notes under fast lines;
- re-struck held pitches.

Three new string checks:
- double_onset;
- restrike;
- double_rate (0.5 quarter), with repeated identical double stops exempt.

Five movements were decoded under the draft rules for that review
(`headroom/data/out/ou_band_masked_v4draft/`, idx 22, 39, 42, 67, 148). They are review material only,
and the run below regenerates them from scratch.

**What is re-run.** Everything in A1/A2, with masks from checker-v4. The trio decides (rule, margin and
threshold unchanged); duo, solos and piano are secondary. Results go to `decoding/results/v4/`.

**Added reference system: Ou et al. + repair** (`decoding/repair.py`; deterministic, CPU, no model):
- It walks the *unconstrained* Ou output in time order, then pitch.
- It keeps each note in Ou's part if the frozen checker allows it there.
- Otherwise it tries the other parts (nearest in register first), then an octave shift (±12) in Ou's
  part, then an octave shift in the other parts.
- It drops the note only if none of these is legal.

Why: the user observed that masking deletes notes that should have been routed to another
instrument. 6.2% of Ou's trio violin notes are below the violin's range, and 96% of those fit
the viola or cello. A blocking baseline that cannot re-route is weaker than the obvious
post-processing. Repair is reported next to masking in every table and in the Step 5 comparison.
It **does not enter the gate decision**, which remains masked vs unconstrained.

### A4 (2026-10-14, before any checker-v5 masked output): checker-v5

**Why.** The user's review of Bridge bars 60–75 (Block 4) found a triple stop that checker-v4 passes
but which is unplayable: violin G3 + E♭4 + E♭5 as an eighth, straight into 16ths.

**checker-v5 (tag `checker-v5`, METRICS 1.5.0-draft; REVIEW R43):**
- violin and viola triple-stop stretch 5 → 4 semitones (normal hand position; U15);
- new `triple_recover`: ≥ 1 quarter from a 3+-note onset to the next onset in the part (U19);
- everything else is unchanged.

**Re-run** (`decoding/run_v5.sh`, GPU 1 only):
- masked Ou et al. for trio, duo and solo violin (the regimes with triple stops; solo flute and
  piano are unaffected by string rules);
- the gate for each, with the same decision rule;
- the repair baseline;
- the headroom re-measurement (`headroom/results_v5`).

Checker-v4 outputs are kept (`*_checker-v4`). The deciding regime stays the trio.

## Result (trio, 150 movements, 2026-10-08, checker-v1)

Rule applied as written (`python -m decoding.gate --regime trio`; data: `decoding/results/trio/`).

| System | D (worst check, per 100 notes) | 95% CI | Note_i F1 | Note F1 | Mel F1 | Harmony | Output notes |
|---|---|---|---|---|---|---|---|
| Ou et al., unconstrained | 5.12 (chord size) | [4.65, 5.59] | 0.498 | 0.672 | 0.586 | 0.804 | 773,065 |
| **Ou et al., masked** | **0.00** | [0.00, 0.00] | **0.508** | **0.685** | **0.630** | 0.796 | 647,731 |
| Continuity (rule-based) | 0.15 (range) | [0.11, 0.18] | 0.678 | 1.000 | 0.853 | 1.000 | 523,196 |
| AMT (secondary, 32-bar window) | 0.09 | — | 0.434 | 0.463 | 0.859 | 0.660 | — |

Paired fidelity loss, Δ = unconstrained − masked (negative = masking *improves* fidelity):

| | Δ | 95% CI |
|---|---|---|
| Note_i F1 (primary) | −0.011 | [−0.015, −0.006] |
| Harmony (co-primary) | +0.009 | [+0.007, +0.011] |
| Note F1 | −0.013 | [−0.017, −0.009] |
| Mel F1 | −0.045 | [−0.052, −0.038] |

**Verdict: outcome 1.** Blocking reaches exactly 0 violations. Both primary CIs lie entirely below the
0.02 margin: Note_i F1 improves, and harmony loses 0.9 points. The masked output has 16% fewer
notes than the unconstrained one, which is still 1.24× the source, so it isn't sparse.

Masking diagnostics: 647,731 notes committed, 0 with a violation, 0 steps where every token was
masked, 0 bars where the parsed output differed from the checker's notes.

## Result under amendment A1 (checker-v2, METRICS 1.1.0-draft, 150 movements each, 2026-10-08)

Data: `decoding/results/v2/<regime>/gate.json`. Run by `decoding/run_v2.sh` (log `decoding/logs/v2_chain.log`).

**Masking diagnostics.** In every regime, 0 committed notes carry a violation and 0 steps had every
token masked. Solo flute had 5 bars where the parsed output differed from the masker's notes, and
those leave a residual D of 0.002.

Violations per 100 notes, worst check (D) with 95% CI. Fidelity is measured against the source.

| Regime | System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Notes |
|---|---|---|---|---|---|---|---|
| **trio (deciding)** | Ou unconstrained | 9.12 [8.73, 9.53] multistop | 0.498 | 0.672 | 0.586 | 0.804 | 773,065 |
| | **Ou masked (v2)** | **0.00** [0, 0] | 0.489 | 0.671 | 0.645 | 0.789 | 610,735 |
| | continuity | 1.35 [1.21, 1.50] multistop | 0.678 | 1.000 | 0.853 | 1.000 | 523,196 |
| | naive | 5.97 multistop | 0.431 | 1.000 | 0.724 | 1.000 | |
| | AMT (secondary, 32 bars, ~41% copied) | 0.23 multistop | 0.434 | 0.463 | 0.859 | 0.660 | |
| duo | Ou unconstrained / masked | 13.23 / 0.00 | 0.506 / 0.488 | 0.749 / 0.708 | 0.511 / 0.597 | 0.832 / 0.792 | ratio 0.73 |
| solo violin | Ou unconstrained / masked | 17.75 / 0.00 | 0.522 / 0.486 | 0.903 / 0.629 | 0.475 / 0.517 | 0.861 / 0.735 | ratio 0.68 |
| solo flute | Ou unconstrained / masked | 249.96 (simult.) / 0.002 | — | 0.795 / 0.321 | 0.422 / 0.519 | 0.767 / 0.470 | ratio 0.29 |
| piano | Ou piano unconstrained / masked | 42.58 [8.55, 113.3] duplicate / 0.00 | — | 0.290 / 0.284 | 0.143 / 0.144 | 0.587 / 0.581 | ratio 0.95 |

Paired Δ = unconstrained − masked, 95% CI (primary: Note_i F1 and harmony; margin 0.02):

| Regime | Δ Note_i F1 | Δ Harmony | Δ Note F1 | Δ Mel F1 | Rule's verdict |
|---|---|---|---|---|---|
| **trio** | +0.009 [+0.004, +0.014] | +0.015 [+0.013, +0.018] | +0.001 | −0.060 | **outcome 1** |
| duo | +0.018 [+0.013, +0.023] | +0.040 [+0.037, +0.044] | +0.040 | −0.086 | outcome 2/3 |
| solo violin | +0.036 [+0.031, +0.041] | +0.126 [+0.122, +0.131] | +0.274 | −0.041 | outcome 2/3 |
| solo flute | n/a (0 by construction) | +0.297 [+0.287, +0.307] | +0.474 | −0.097 | outcome 2/3 |
| piano | n/a (0 by construction) | +0.006 [+0.001, +0.011] | +0.007 | −0.002 | outcome 1 (harmony only) |

**Verdict (trio, deciding): outcome 1 again.** Under checker-v2, masking reaches 0 violations. Both
primary CIs sit below the 0.02 margin, but harmony's upper bound (0.018) is now close to it, where
under checker-v1 it was 0.011.

**Secondary results (not deciding).**
- Masking costs real fidelity as the target shrinks. Duo, solo violin and solo flute all clear the
  margin. Solo flute masked keeps only 29% of the unconstrained notes: the band model writes chords
  for the flute, and the mask can only delete them, not re-voice them.
- Ou's unconstrained piano D comes from a few degenerate movements that repeat the same key (wide
  CI). Masking removes those at no cost.
- For solo flute and piano, Note_i F1 is 0 by construction, because no source instrument matches.
  Their verdicts therefore rest on harmony alone. This is a known gap in the metric, not a result.

MuseScore view (v1-masked vs v2-masked vs unconstrained, red = checker-v2 violation):
`decoding/results/examples/067_bars1-16_checker-v2/`. In the excerpt, the checker-v1-masked output
has 134 checker-v2 violations among 302 notes, and the checker-v2-masked output has 0 among 253.

## Result under amendment A2 (checker-v3, METRICS 1.2.0-draft, 150 movements each, 2026-10-09)

Data: `decoding/results/v3/<regime>/gate.json`. Run by `decoding/run_v3.sh` (log `decoding/logs/v3_chain.log`).

**Masking diagnostics.**
- Every regime: 0 committed notes with a violation, and 0 steps where every token was masked.
- Bars where the parsed output differed from the masker's notes: trio 1, duo 5, solo violin 2,
  solo flute 5, piano 0. Only solo flute leaves a residual D (0.002).

| Regime | Ou unconstrained D | Masked D | Notes kept | Δ Note_i F1 | Δ Harmony | Δ Note F1 | Δ Mel F1 | Verdict |
|---|---|---|---|---|---|---|---|---|
| **trio (deciding)** | 12.58 [11.96, 13.29] triple_onset | 0.00 | 67% | **+0.033 [+0.027, +0.039]** | **+0.041 [+0.038, +0.044]** | +0.021 | −0.062 | **outcome 2 or 3** |
| duo | 18.36 triple_rate | 0.00 | 58% | +0.057 [+0.050, +0.065] | +0.088 [+0.083, +0.093] | +0.090 | −0.088 | outcome 2/3 |
| solo violin | 24.08 triple_rate | 0.00 | 52% | +0.081 [+0.074, +0.089] | +0.204 [+0.198, +0.210] | +0.356 | −0.047 | outcome 2/3 |
| solo flute | 249.96 simultaneity | 0.002 | 29% | n/a (0 by construction) | +0.297 [+0.287, +0.307] | +0.474 | −0.097 | outcome 2/3 |
| piano | 42.58 duplicate | 0.00 | 95% | n/a (0 by construction) | +0.006 [+0.001, +0.011] | +0.007 | −0.002 | outcome 1 (harmony only) |

References for the trio:
- continuity: D 1.35 (multistop), Note_i F1 0.678;
- naive: D 8.46 (triple_rate);
- AMT (secondary; 32 bars, ~41% copied control line): D 0.32 (bow).

**Verdict (trio, deciding): outcome 2 or 3.**
- Masking reaches 0 violations.
- The Note_i F1 and harmony losses both have CI lower bounds above the 0.02 margin.
- Masked Ou et al. keeps 67% of its notes.

**Secondary results.**
- **Cost grows as the ensemble shrinks.** The fidelity cost of masking rises monotonically:
  harmony loss is 0.041 (trio), 0.088 (duo), 0.204 (solo violin). This is the outcome-3 shape
  ("blocking degrades as constraints tighten"). Telling 2 from 3 needs a trained model.
- **Piano is unchanged from A1.** The checker-v3 rules are string-only.
- **Mel F1 improves under masking everywhere.** Deleting accompaniment notes clears the top line.
  This is not evidence of better fidelity.

Under the checker-v3 rules the masked trio has 0 violations in the MuseScore excerpt
(`decoding/results/examples/067_bars1-16_checker-v3/`). The checker-v2-masked trio has 58 red notes.

## Result under amendment A3 (checker-v4, METRICS 1.3.0-draft, 150 movements each, 2026-10-12)

| Regime | Ou unconstrained D | Masked D | Notes kept | Δ Note_i F1 | Δ Harmony | Δ Note F1 | Δ Mel F1 | Verdict |
|---|---|---|---|---|---|---|---|---|
| **trio (deciding)** | 12.58 [11.96, 13.35] triple_onset | 0.0002 (multistop) | 58% | **+0.086 [+0.078, +0.094]** | **+0.092 [+0.087, +0.099]** | +0.089 | +0.039 | **outcome 2 or 3** |
| duo | 18.36 triple_rate | 0.00 | 49% | +0.119 [+0.111, +0.128] | +0.148 [+0.142, +0.155] | +0.172 | +0.014 | outcome 2/3 |
| solo violin | 24.08 triple_rate | 0.0009 | 44% | +0.148 [+0.139, +0.158] | +0.265 [+0.258, +0.272] | +0.425 | +0.047 | outcome 2/3 |
| solo flute | 249.96 simultaneity | 0.0016 | 29% | n/a (0 by construction) | +0.297 [+0.287, +0.307] | +0.474 | −0.097 | outcome 2/3 |
| piano | 42.58 duplicate | 0.00 | 95% | n/a (0 by construction) | +0.006 [+0.001, +0.011] | +0.007 | −0.002 | outcome 1 (harmony only) |

Piano is unchanged from A2, because the checker-v4 rules apply to strings only.

References for the trio under checker-v4:
- continuity: D 10.18 (double_onset), Note_i F1 0.678;
- naive: D 9.35 (double_rate);
- Ou et al. + repair: D 0, Note_i F1 0.390, harmony 0.758 (not part of the decision);
- AMT (secondary; 32 bars): D 1.76 (double_onset).

**Verdict (trio, deciding): outcome 2 or 3,** as under A2.
- The masking cost roughly doubles from checker-v3: harmony loss is 0.092, against 0.041.
- Masked Ou et al. keeps 58% of its notes.
- Repair re-routes rather than drops, but scores lower than masking on Note_i F1 and higher on harmony.

The trained arranger (MODEL.md), masked, beats both playable Ou et al. variants on fidelity at D = 0.

Excerpts: `decoding/results/examples/checker-v4/`. The same excerpts with the arranger's
output are in `decoding/results/examples/arranger-v1/`.

## Result under amendment A4 (checker-v5, METRICS 1.5.0-draft, 150 movements each, 2026-10-14)

| Regime | Masked D | Notes kept | Δ Note_i F1 | Δ Harmony | Verdict |
|---|---|---|---|---|---|
| **trio (deciding)** | 0.0005 | 56% | **+0.090 [+0.082, +0.098]** | **+0.098 [+0.092, +0.105]** | **outcome 2 or 3** |
| duo | 0.0003 | 46% | +0.127 [+0.118, +0.136] | +0.159 [+0.152, +0.166] | outcome 2/3 |
| solo violin | 0.000 | 40% | +0.164 [+0.153, +0.176] | +0.288 [+0.281, +0.295] | outcome 2/3 |

Δ = unconstrained − masked. **Verdict (trio, deciding): outcome 2 or 3, unchanged from A3.** The masking
cost rises slightly with the stricter triple-stop rules (trio harmony loss 0.092 → 0.098). Solo flute
and piano are unaffected by string rules and were not re-run.
