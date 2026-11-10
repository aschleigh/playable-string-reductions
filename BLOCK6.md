# Block 6 brief: solo piano and solo flute (PROPOSAL, awaiting approval)

Status: **approved 2026-10-16 (R63: all six recommended options).** Originally a **proposal, 2026-10-16.** Nothing has been run or changed. Every rule, threshold and criterion
below is a proposal. Research-consequence decisions are marked **[U]**.

State before this block: BLOCK5.md (control-S2c is the current string system, R59), REVIEW R1–R61,
DECODING.md (the Ou et al. piano and solo-flute baselines).

**Goal.** Extend the playable-reduction approach from strings to two instruments at opposite extremes:
- **Solo flute: very little capacity.** One note at a time, a fixed range (C4–C7), and the player must
  breathe. The reduction is mostly *choosing*: which line to follow, and when.
- **Solo piano: a lot of capacity, with different limits.** Ten fingers in two hands, a reach per hand, and
  large jumps possible but not instant. Most of the quartet fits; the question is how to voice it under the
  hands.

**The thesis question:** does the same method (a playability checker, rule-built supervised targets, a masked
arranger) hold up when the constraints change shape completely? For strings the limit was double stops;
for flute it is simultaneity and breath; for piano it is hand span and hand movement.

---

## Step 0: what already exists (checked 2026-10-16)

| Piece | Flute | Piano |
|---|---|---|
| Checker rules (`instruments.yaml`) | monophonic; range C4–C7 (U6, U7, placeholders) | range A0–C8; ≤ 10 notes; per-hand span 14 semitones, 5 fingers (U8, placeholder); two-hand leap 24 + 12 per quarter (U12, U13, placeholders, "no piano corpus to calibrate on") |
| Ensemble | `solo_flute` | `solo_piano` (one part; the checker splits the hands) |
| Baselines (DECODING.md, checker-v2 era) | Ou et al. band model: unconstrained 250 violations per movement; masked keeps 29% of notes | Ou et al. piano arranger: masked, 0 violations, harmony 0.58 |
| Our arranger | `flute` instrument token exists, never trained | `piano` token exists, never trained |

**Known metric gap:** Note_i F1 is 0 by construction for both, because no source part is a flute or piano
(DECODING.md). Evaluation must rest on instrument-free measures (Step 4).

## Step 1: data

**1a. A piano corpus for calibration** (the only new data needed) **[U]**
- **Purpose:** set the hand span (U8) and hand-leap (U12, U13) thresholds from real piano writing, as the
  string thresholds were set from the quartets (`arrangement/calibrate.py`, envelopes).
- **Recommended source:** OpenScore Lieder (CC0, the same project and MuseScore format as the quartets;
  over 1,000 songs, each with a piano part). Its accompaniments cover a wide range of keyboard writing.
  Its availability and licence would be checked before download. Alternatives: piano music in other
  public-domain MuseScore collections.
- **Use:** calibration only (envelopes), not training. Results recorded in UNSOURCED.md, then
  **checker-v6** (piano thresholds only; strings unchanged), tagged, with the baselines re-run under it.

**1b. Flute: no corpus** **[U]**
- Range stays U6/U7 (standard compass). There is no flute corpus to calibrate breath on, and no tempo
  in the data, so **breath is not a checker rule**. It is a target rule (Step 2), soft, so no unsourced
  hard threshold enters the checker.

**1c. Human piano reductions of quartets: not needed** (optional)
- Published piano reductions of Haydn or Beethoven quartets exist (IMSLP), but only as scans; optical
  music recognition would make them noisy. They could serve as a listening reference later, not as targets.

**Training data:** the same 476 training quartets. The targets come from rules (Step 2), as S2 did for
strings, so no new training data is needed.

## Step 2: rule-built targets (like S2)

**F targets (flute)**, per movement:
1. **The melody line:** the top-tier note at each onset (`voice_tiers`), monophonic; outside C4–C7 it moves
   by octaves into range.
2. **Weaving [U]:** when the top voice rests for at least a bar, take the most active other voice (inner
   before bass) until the melody returns, at an octave that fits. Recommended: on. Off makes the flute
   target nearly the trivial "top line" baseline.
3. **Breath (soft) [U]:** after at most 8 quarters of continuous notes, the note before the next
   melodic boundary (a leap of a fifth or more, or a long note) is shortened by an eighth to leave a breath.
   Tempo-blind, like every other rule; reported, not enforced by the checker.
4. Everything else is dropped.

**K targets (piano)** ("K" for keyboard; not "P", which was the parked idiom model):
1. Keep every source note, in its octave, in the one piano part; unisons merged (decode v2).
2. Visit notes in time order, then by tier (top, bass, inner), as S2. Each takes the first option that the
   frozen checker accepts (span, fingers, hand leap): its own octave; then an octave toward the middle
   (the bass down only if the left hand is free); then **drop**, inner voices first.
3. Melody and bass are never dropped while an octave option is feasible.

**Calibration before any training** (on 200 training movements, as S2b): report the note ratio, the melody
retention, and how often each option is used. For K: hand-span use and leaps against the piano corpus.

## Step 3: models

- **One arranger for all four regimes [U]** (recommended): fine-tune control-S2c on trio + duo (S2c targets)
  + flute (F) + piano (K) together, the regime given by the instrument tokens. Claim: one model learns
  instrument-specific playability. Fallback: separate fine-tunes per instrument, if the joint model loses
  string quality on the dev split (melody retention −0.005 or worse, or string double stops above S2c's).
- Same recipe as control-S2: 3,000 steps (a second 3,000 if the dev loss is still falling), GPU 1 only.
- **Decoding:** masked (checker-v6), melody-first, as for strings.
- **Realisation vocabulary:** unchanged (plain, arpeggiate, repeat, tremolo, octave double). No new keyboard
  textures (Alberti bass and so on) in this block: the arranger reassigns and re-octaves source notes, it does
  not compose accompaniment.

## Step 4: evaluation (METRICS 1.6.0-draft)

Instrument-free measures, since Note_i F1 is 0 by construction:
- **Melody retention** (top tier; count and duration), **bass retention** (piano), **harmony** (beat chroma);
- **note ratio**, **interventions**, **hard violations** (masked 0 by construction; unmasked reported);
- **flute:** monophony by construction; breath gaps (count and longest unbroken run, in quarters); the
  share of notes taken from non-melody voices (weaving);
- **piano:** per-hand span use and hand-leap distributions, against the piano corpus (Step 1a); notes per
  hand; the share of source notes kept.

**Baselines:** Ou et al. piano arranger (masked and unconstrained); Ou et al. band model for solo flute (masked);
"top line" (the trivial flute baseline: highest note at each onset, folded into range); continuity; naive;
**AMT, secondary**, wherever it can produce a solo flute or piano output (if it cannot, say why).

## Step 5: selection and one confirmatory test

- **Dev split only** for every choice: weaving on/off, breath length, joint against separate models.
- **Criterion D (pre-registered with this brief), per regime, against Ou et al. masked:**
  1. hard violations 0 (masked) and unmasked violations per 100 notes lower than Ou unconstrained's;
  2. melody retention (count): CI lower bound of Δ > 0;
  3. harmony: CI lower bound of Δ > −0.02;
  4. interventions ≤ 5% of notes.
  - **Flute only:** also melody retention ≥ the "top line" baseline's − 0.01, so that the model is not worse
    than the trivial line.
- **Movements:** the 145 evaluation movements. This is the **first** confirmatory use for flute and piano,
  but the movements have been used for strings, so this is reported as a caveat. The 21 unused ABC Beethoven
  movements are a secondary, descriptive check if they parse.

## Step 6: listening

MusicXML only (R61): Bridge 60–75 and Haydn 1–16 (the usual excerpts), plus one full movement each, for
flute and piano, from control-F/K on the review movements. Your verdicts feed rule changes before the
confirmatory test, as with strings.

## Compute

GPU 1 only; ≤ 16 CPU workers. Estimate:
- corpus download and calibration: half a day (mostly parsing);
- targets: 1 hour each;
- joint fine-tune: 1–2 hours;
- dev decodes and excerpts: 2 hours;
- confirmatory decodes and evaluation: 3 hours.

## Not in this block

- **Duo infilling** (Step 6 of Block 5): after Block 6, as agreed.
- **P, the idiomatic model:** parked (R57). *Amendment A (proposed) brings it back as P v2 for strings, Step A4.*
- **Composing accompaniment** (new keyboard figures): a later block, if wanted.

## Decisions requested

1. **Piano corpus:** OpenScore Lieder for calibration (recommended), then checker-v6 for piano only.
2. **Flute breath:** a soft target rule (≤ 8 quarters before a breath), not a checker rule (recommended).
3. **Flute weaving:** take another voice when the melody rests for a bar or more (recommended: on).
4. **One joint arranger** for trio, duo, flute and piano (recommended), with separate models as the fallback.
5. **Criterion D** as above, including the flute's "not worse than the top line" item.
6. **Confirmation** on the 145 (first use for these regimes; caveat stated), plus the 21 ABC movements as
   secondary.

---

# Progress (after approval, R63)

## Step 1: piano calibration and checker-v6 (R65, R66)

- OpenScore Lieder (CC0): 1,462 songs, 1,425 with one piano part.
- Sounding sets (the old basis) are dominated by held notes and pedal: held-out songs exceed the 14-semitone placeholder
  on 3.5% of multi-note onsets; dev max 43. Struck sets: dev 99.9th percentile 16.7, held-out above 16: 0.12%.
- **checker-v6 (piano only):** hand rules on struck notes; span 16 (U8); hand leap 18 + 32 per quarter (U12, U13).
  1,325 tests pass; tagged. Ou et al. piano masked regenerated under v6 (`decoding/run_v6.sh`).

## Step 2: targets (R64, R67)

- **Flute weaving needs no rule:** the top tier is a skyline, so the line already moves to the next-highest voice.
  The F target is therefore close to the "top line" baseline; melody identification would be the substantive flute
  problem (flagged).
- **Breath** is limited by the vocabulary (a long note cannot be shortened, only dropped): median longest unbroken run
  48 quarters (v1) / 40 (v2) on 15 dev movements. control-J uses v1; a "shortened" realisation is a later step.
- Train split, checker-v6: piano keeps 99.8% of source notes; flute keeps the top line (31% of notes).

## Step 3: control-J, the joint arranger

From control-S2c, `--targets joint` (trio/duo S2c + flute/piano F/K), 3,000 steps, 88,904 windows, GPU 1.

## Criterion D, operational form (frozen 2026-10-16, before any evaluation-set decode; `model/confirm6_eval.py`)

Per regime (piano, solo_flute), control-J masked against Ou et al. masked, 145 movements, paired 95% movement bootstrap:
1. control-J masked has 0 hard violations, and Δ unmasked violations per 100 output notes (control-J unmasked − Ou
   unconstrained) has a CI upper bound < 0;
2. Δ melody retention (top tier, count, harness) CI lower bound > 0;
3. Δ harmony CI lower bound > −0.02;
4. interventions ≤ 5% of input notes (point estimate);
5. flute only: Δ melody retention (control-J − top line) CI lower bound > −0.01.
**Joint fallback (decision 4), checked on dev before the test:** separate models if control-J's dev melody retention
(duration, M) falls more than 0.005 below control-S2c's in trio or duo, or any string part's dev double stops rise by more
than 0.5 per 100 notes.
**AMT:** not available for piano or flute (its outputs exist for the trio only), so it cannot be a baseline here.
**Order:** the confirmatory test (`model/run_block6_c.sh`) runs only after the user's listening review (Step 6).

---

# Amendment A: an RL stage (approved 2026-10-24, R73)

Status: **approved 2026-10-24 (R73: all six recommended options).** Originally a proposal; at approval nothing had been run or changed. It changes nothing above that is already done. It inserts
an RL stage between the control-FK2 listening review (Step 6) and the confirmatory test (Step 5), and brings back
P, the parked idiomatic model, for strings. Research-consequence decisions are marked **[U]**.

**Why.** Since R55/R57 the project has had no RL in it: every current system is a supervised fine-tune on rule-built
targets, with the checker as a decode-time mask. The user wants RL in the project. The thesis question becomes:

> Rule-built supervised targets plus a masked arranger make reductions playable. **Does RL on top of that
> supervision improve what the rules specify only crudely?** (flute: which line, when to breathe; piano: voicing
> under the hands without the checker stepping in; strings: whether a part looks like real writing for that instrument)

**What the RL week (R33–R41) already settled, reused here:**
- **Masked GRPO works mechanically** (`model/grpo.py`, `tests/test_grpo.py`): PPO-clipped, group-normalised,
  KL to the frozen base, over the stored masks.
- **The constraint can be learned under the mask:** the conditional feasibility term (R34b, `--feas`: −log of the
  feasible share of the *non-DROP* probability) lowered interventions (rl-AZ2) without rewarding drops.
  (Correction to WEEK_SUMMARY lesson 2: it was true of the approved objective, not of RL as such.)
- **Hacks to guard against, each seen once:** splitting held notes into repeats (rl-C, rl-AZ2, fixed by
  "kept only if held ≥ 75%", setting A2); dropping notes (rl-AZ, fixed by excluding DROP); λ too high cuts the
  penalised thing by dropping notes (rl-SA3Z).
- **What failed was starting points and rewards, not RL:** RL from v2b had to undo a bad texture. Here it starts from
  systems that already have the right texture (control-FK2, control-S2c) and is asked for refinements.

## Step A1: GRPO for flute and piano (code)

- `model/grpo.py`: regimes `piano` and `solo_flute`; part/octave/realisation sizes read from the checkpoint, as
  `model/decode.py` does since R70 (control-FK2 has n_real 6, with CUT); CUT handled in the reward (A2).
- **Contexts:** control-FK2's greedy masked decodes of the train windows (as R52 for control-S2b).
- **Tests:** the existing GRPO tests pass for all four regimes; a new test that CUT and the one-part ensembles replay
  deterministically.

## Step A2: rewards (pre-registered here)

Per 16-quarter window, from the M2 structure (R40): duration-weighted fidelity, a note credited only if held
≥ 75% of its written length (anti-repeat), 0.8 credit an octave away. Plus the conditional feasibility term
(R34b, weight 1.0) in the loss for every run.

**Flute, R_F:**
- **M_top:** duration-weighted retention of the top tier. **A CUT note counts as held** (CUT is the breath mechanism,
  R70; this fixes the R71 artefact where M fell to 0.881).
- **+ 0.25 · H** (harmony, beat chroma, as before).
- **− λ_B · breath shortfall:** max(0, longest unbroken run in the window and its context − 12 quarters) / 16.
  12 quarters is the F3 rule's "breath by 12 quarters" **[U]**.
- **− κ_C · excess CUT share:** max(0, CUT share − 1.5 × the F3 target's CUT share in that window). Guards the obvious
  hack (CUT everything to collect breaths at no melody cost).
- **Floor (G, as before):** top-tier retention ≥ 0.9 × the F3 target's.
- **Settings:** λ_B ∈ {0.5, 1.0}, κ_C = 2.

**Piano, R_K:**
- **Duration-weighted retention**, weights top 1.0, bass 1.0, inner 0.5; **+ 0.25 · H**.
- **The feasibility term carries the main signal:** control-FK2 needs the checker on 1.8% of piano notes; RL should
  bring that and the unmasked violations (criterion D item 1) down.
- **Floors:** top and bass ≥ 0.9 × the K target's.
- **Settings:** feas ∈ {1.0, 3.0}.

**Expected size of the effect (stated before running):**
- **Flute:** small on melody (control-FK2 0.940, top line 0.949, and the F target is close to the top line, R64);
  the room is in breath placement (median longest run 39.5 quarters).
- **Piano:** interventions 1.8% → under 1%, if it works.
- **Either way:** "RL adds little on top of good supervision" is a usable thesis result, reported as such.

## Step A3: selection (dev split only)

- **Runs:** 4 (2 flute, 2 piano), from control-FK2, up to 1,000 steps each; validation every 100 steps on 20 dev windows;
  lr 1e-5, β 0.02, G 8, as the earlier runs.
- **A checkpoint is eligible** if, on the 61 dev movements (`model/dev_fk.py`, as R71), against control-FK2:
  1. melody retention (count) ≥ control-FK2's − 0.005; piano bass also;
  2. interventions ≤ control-FK2's;
  3. **detectors (fixed now):** note ratio within ±0.05 of control-FK2's; repeat share ≤ control-FK2's + 0.02; drop
     share ≤ control-FK2's + 0.02; flute CUT share ≤ 1.5 × the F3 targets'; piano notes per hand within ±10%;
  4. flute only: median longest unbroken run ≤ control-FK2's.
- **Among eligible:** the highest mean dev reward. **None eligible:** control-FK2 goes to the test unchanged, and the
  RL result is reported as negative.
- **Listening:** MusicXML excerpts of the selected run (the usual Bridge 60–75 and Haydn 1–16) before the test. The
  user's verdict can veto it.

## Step A4: strings, RL with P v2 (the parked idiomatic model) **[U]**

From the BLOCK5 P v2 proposal, built only after the user approves this amendment:
- **P v2 score**, per part, against real dev parts of the same instrument:
  - two-sided: −|z| of the mean log-likelihood (too predictable is atypical too: this is what let restrike16 pass);
  - plus a histogram distance (durations, intervals, voices, re-strikes) to the real parts.
- **New gate, before any RL:**
  - It must rank real > control-S2c > v2b > every hack on the dev split.
  - Hacks: the four old ones (restrike16, up2oct, shuffle, dyads) plus four **not seen while designing P v2**,
    defined now and frozen. **sustain** (every note held to the next onset, no rests). **arp16** (every chord broken
    into 16ths). **mel-copy** (every part plays the melody in octaves). **mid-clamp** (every note folded into the
    instrument's middle octave).
  - **Fails → no string RL** (pre-registered, as R55), and strings stay control-S2c.
- **Passes →** RL from control-S2c, setting MI-style (M2 + λ_I · P v2 term, floors top and bass, feas 1.0),
  λ_I ∈ {0.5, 1.0}. Same selection rule as A3, with string double stops ≤ control-S2c's + 0.5 per 100 notes as an
  extra detector.
- **Confirmation:** the strings' confirmatory set has been used twice (R46, R56). A third use needs the user's approval
  **[U]**. Recommended: report string RL on dev only, as development evidence, and keep the 145 for flute and piano.

## Step A5: the confirmatory test (Step 5, extended)

- **Criterion D unchanged** (frozen 2026-10-16), applied to the system chosen in A3 (RL if eligible, else control-FK2).
- **New criterion E (pre-registered here), RL against control-FK2, per regime, paired 95% movement bootstrap.** Run
  only if an RL checkpoint was selected.
  1. interventions: Δ CI upper bound < 0;
  2. melody retention (count): Δ CI lower bound > −0.005;
  3. harmony: Δ CI lower bound > −0.01;
  4. flute: median longest unbroken run Δ < 0 (point estimate).
- **Reporting:** control-FK2 appears as a reference row either way. E holds → "RL improves on the supervised system"
  in that regime; it fails → reported as a negative result.

## Compute

GPU 1 only; ≤ 16 CPU workers (the earlier runs used 48 rollout workers: it will be cut to 16, so a run is slower).
- A1 code and tests: half a day;
- contexts: 1 hour;
- 4 flute/piano runs: about 4–6 hours each, sequential;
- P v2 and gate: 2 hours; 2 string RL runs if the gate passes: about 10 hours;
- dev selection, excerpts, confirmatory test: 4 hours.

## Decisions requested (Amendment A)

1. **Add the RL stage for flute and piano** (A1–A3) before the confirmatory test (recommended).
2. **Rewards and settings as in A2,** including the 12-quarter breath target and CUT counted as held (recommended).
3. **Selection rule and detectors as in A3,** with the user's listening veto (recommended).
4. **Bring back P as P v2 for strings,** with the new gate and its four new hacks (A4) (recommended: yes, after the
   flute/piano runs, so GPU 1 runs one thing at a time).
5. **String RL on dev only,** with no third use of the 145 (recommended), or a third confirmatory use (with the caveat).
6. **Criterion E** as in A5 (recommended).
