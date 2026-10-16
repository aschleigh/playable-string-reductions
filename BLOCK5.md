# Block 5 brief: an idiomatic-part term, and RL from control-S2 (PROPOSAL, awaiting approval)

Status: **approved 2026-10-15 (R51: all six recommended options).** Originally a **proposal, 2026-10-15.** Nothing in this brief has been run beyond the S2b target calibration
(Step 1a), which the user approved ("the open rule looks good"). Every weight, threshold and
formulation below is a proposal. Research-consequence decisions are marked **[U]**.

State before this block: BLOCK4.md (R44–R47), `model/results/confirm/CONFIRM.md`, WEEK_SUMMARY.md.

**Goal.** Block 4 made the parts *playable* (control-S2: double stops at or near real-part levels,
melody kept, interventions about 1%). Nothing in the objective asks whether each part *looks like a real
violin, viola or cello part*. Block 5 adds that term, checks it on the dev split before using it, and
then runs RL from control-S2 with it.

**User additions (2026-10-15), all carried here:**
- cello may take over material up to **high D in thumb position (D5)** (U20);
- cello triple stops in **extended position** are allowed (U14, stretch 4: unchanged, now user-confirmed);
- viola double stops **slightly stricter** (U21);
- **"a bit of generative infilling (but emphasis on a bit, only when absolutely necessary)"**: a later,
  optional phase (Step 6).

---

## Step 0: state check (read-only)

- **Checker:** checker-v5 unchanged since the tag. **Metrics:** METRICS 1.5.0-draft.
- **Splits:** train / val (dev) / eval = 476 / 61 / 150, pairwise disjoint. The 5 review movements
  stay excluded from every test.
- **Checkpoints:** arranger-v2b, control S, control-S2 present.
- **Fresh data:** count the quartet movements in `raw_corpora/` that are outside the 687 split
  movements, as a possible fresh confirmation set (see Step 5).

## Step 1: S2b targets and control-S2b

**1a. S2b targets** (`model/targets_s2.py`, the S2 rules plus two changes):
- **U20:** a note moved into the cello may go up to D5 (MIDI 74), not G4. Above that, the octave below.
- **U21 (viola, stricter):** a source double stop made only of inner-voice notes is accepted in the
  viola only if no other viola double stop began within `VIOLA_INNER_DS_GAP` quarters before it.
  Otherwise the note takes its next option (another part, an octave, or a drop: the viola keeps its
  upper note, since notes are visited highest first). Double stops involving the melody or bass are
  not touched.
- **Calibration:** on 200 training movements, the smallest gap that brings the viola's target rate to
  about **4.5 per 100 notes** (real viola 5.1; S2 was 6.1). Result in the progress section below.

**1b. control-S2b:** the control-S2 recipe unchanged (fine-tune from v2b on the S2b targets, all 476
train movements, 3,000 steps, GPU 1).

**1c. Dev check (61 dev movements, masked, melody-first):** report double stops per part, melody
retention, interventions, inner retention and harmony, against control-S2. Expected: viola ≤ 4.5, the
rest about unchanged. control-S2b replaces control-S2 as the Block 5 base if the viola rate falls and
melody retention does not fall by more than 0.005 **[U]**.

## Step 2: the idiomatic part model P

**Data.** The real parts of the 476 training quartets: Vn1, Vn2, Va, Vc (1,904 parts). Real dev
parts (61 × 4) are held out for calibration only.

**Events** (one per onset in the part; chords are one event):
- pitch interval from the previous event's top note (clipped ±24, plus "rest" and "first");
- register: top note's MIDI pitch, bucketed in 3-semitone bins within the instrument's range;
- duration in quarters, log-bucketed (16th to whole note, 12 buckets), and rest before the event;
- held or re-struck (does the event repeat a still-sounding pitch?);
- number of voices sounding (1, 2, 3+) and the double-stop interval class;
- beat position (bucketed by metre position from the source's time signature);
- an instrument token at the start (violin, viola, cello). Vn1 and Vn2 are both "violin".

**Model.** A causal transformer, 4 layers × 256 wide, 4 heads, about 2–3M parameters, context 512
events; next-event prediction, each feature a separate softmax head (summed log-likelihood). Trained
on GPU 1, about an hour.

**Score.** For an output part, the mean per-event log-likelihood under P, as a **z-score against real
dev parts of the same instrument**, computed on windows of 64 events, so movement length does not
matter. The trio parts are scored as violin, viola, cello. **The duo cello [U]:** it carries viola
material, so it is scored against real cello parts *and* real viola parts, taking the better of the two
(recommended), rather than as a cello only.

## Step 3: validation gate (dev split, before any RL)

P is used only if, on the 61 dev movements, it ranks part outputs in this order for each instrument:

**real dev parts > control-S2(b) > v2b > hacked outputs.**

- **Hacked outputs** (built, not trained): rl-AZ2's repeat-op outputs; v2b with every note re-struck as
  sixteenths; the melody shifted two octaves; random part reassignment; every inner note made a double stop.
- **Pass rule (fixed now):** the pairwise AUC of each adjacent pair (per part, over the dev movements) is
  ≥ 0.70, and every hack set is below v2b with AUC ≥ 0.90 **[U]**.
- **If it fails:** report which pair and stop. No RL with P.
- **Also reported:** P's z for real *eval* parts is **not** computed (no peeking).

## Step 4: RL from control-S2b with the idiomatic term

**Reward:** `R = F_M + λ_I · mean over parts of min(z_part, 0) / 3`, clipped to [−1, 0]. The idiomatic
term only penalises parts *less* idiomatic than typical real parts; there is no reward for being "more
real than real", which removes the main route to exploiting P.

**Kept from Block 4:** the KL anchor (now to control-S2b), the duration-weighted melody and bass
retention floors of reward M, the feasibility term, the fixed detectors (repeat share, note ratio, mean
duration ratio), the checker-v5 mask, and melody-first decoding for rollouts.

**Runs:** two settings, **λ_I = 0.5 and 1.0** **[U]**, 400 steps each, GPU 1 only, CPU ≤ 16 workers.

**Selection rule, fixed before either run.** Dev split only:
1. **Eligible** if, in both regimes, the dev melody retention (duration) is ≥ control-S2b's − 0.005,
   interventions ≤ control-S2b's + 0.005, every criterion-B double-stop item still holds on the
   point estimate, and the detectors stay in range.
2. **Among the eligible,** choose the higher mean dev idiomatic z. A difference < 0.1 is a tie, broken by
   higher dev harmony.
3. **If neither is eligible,** report it, and control-S2b is the Block 5 system with no RL.

**Monitoring:** one listening excerpt per run (the Bridge, 022 bars 60–75, a review movement) for the user.

## Step 5: one confirmatory test

**Criterion C (pre-registered with this brief, per regime, against control-S2b masked):**
1. Criterion B, items 1–4, still holds against v2b (viola now ≤ 5.1 on the CI upper bound).
2. **More idiomatic:** Δ mean idiomatic z, CI lower bound > 0.
3. **Non-inferiority:** Δ melody retention (count) CI lower bound > −0.01; Δ harmony CI lower bound > −0.02.

If no RL setting is eligible, control-S2b alone is confirmed against criterion B.

**Which movements [U]:**
- **Recommended:** a fresh set, if Step 0 finds enough unused quartet movements in `raw_corpora/`
  (at least 60, same filtering as the split).
- **Otherwise:** the same 145 evaluation movements, with the caveat stated in every table: this is the
  set's **second** confirmatory use. The R46 result was seen, so it is weaker evidence than a first look.

## Step 6 (later, optional): a bit of generative infilling

The user: "a bit of generative infilling (but emphasis on a bit, only when absolutely necessary)".
Not started until Steps 1–5 are done and the user asks for it. The proposed shape:

- **Only when necessary:** a beat qualifies only if dropping inner voices left it without a chord tone the
  source has: the third or seventh is missing from every part, mostly in the duo (inner retention 0.03).
- **Only from the source:** an infilled note takes a pitch class from the dropped source notes of that beat.
  The model chooses the octave and part, not new harmony.
- **Only a bit:** at most one inserted note per qualifying beat, and a budget of ≤ 2% of output notes
  per movement **[U]**.
- **Only where playable:** under the checker-v5 mask and the S2b no-new-double-stop rule.
- **Reported apart:** inserted notes are flagged in the records and never count as kept source notes.
  Harmony is reported with and without them.

## Compute

GPU 1 only (GPU 0 is Jon's). Target building and evaluation use ≤ 16 CPU workers. Estimate:
- control-S2b, 2 hours;
- P, 1 hour;
- two RL runs, about 8 hours;
- dev and confirmatory decodes, 3 hours.

## Decisions requested

1. Step 1c: control-S2b replaces control-S2 if the viola rate falls and melody holds (−0.005).
2. Step 2: the duo cello scored against cello or viola, taking the better (recommended).
3. Step 3: the gate thresholds (AUC 0.70 adjacent, 0.90 hacks).
4. Step 4: λ_I ∈ {0.5, 1.0}; penalty-only idiomatic term.
5. Step 5: a fresh confirmation set if available (recommended), else the 145 with the second-use caveat.
6. Step 6: deferred; the ≤ 2% budget when it starts.

---

# Progress

## Step 1a: S2b target calibration (2026-10-15)

Calibration on the first 200 training movements, trio, S2b rules with the D5 cello limit
(REVIEW R49, UNSOURCED U20/U21). Double stops per 100 target notes, and retention by source tier:

| Viola gap (quarters) | Violin | Viola | Cello | Top kept | Bass kept | Inner kept |
|---|---|---|---|---|---|---|
| S2 (G4, no viola rule) | 2.57 | 6.11 | 4.64 | 0.9885 | 0.9820 | 0.581 |
| off (D5 only) | 2.57 | 6.11 | 4.54 | 0.9886 | 0.9809 | 0.581 |
| 0.5 | 2.57 | 5.88 | 4.54 | 0.9886 | 0.9808 | 0.579 |
| 1 | 2.57 | 5.28 | 4.54 | 0.9886 | 0.9808 | 0.575 |
| **2 (chosen)** | 2.57 | **4.45** | 4.54 | 0.9886 | 0.9808 | 0.569 |
| 4 | 2.57 | 3.68 | 4.53 | 0.9886 | 0.9808 | 0.564 |

- **Chosen: 2 quarters**, the smallest gap reaching ~4.5 (real viola 5.1).
- **D5 cello limit:** no extra cello double stops; about 10.7k notes moved into the cello now sound
  between G4 and D5, where S2 put them an octave lower.
- **Cello targets** sit at about 4.5 per 100 in both S2 and S2b, above the real 2.5. This is not new:
  control-S2's output was 2.1 on the evaluation set, under the mask. It will be watched in Step 1c.
- **Full build done** (476 movements, trio and duo) -> `model/results/rl/targets_s2b__train.pkl`. Trio: top dropped 0.4%, bass 0.4%, inner 17.6%; the viola rule refused 30,311 options.

## Step 0 (2026-10-15)

- Checker-v5 and METRICS 1.5.0-draft unchanged; checkpoints present.
- **Fresh data:** all 687 OpenScore movements are in the split. ABC has 21 Beethoven movements outside it
  (Op. 59/1, 59/2, 74, 95, 132), fewer than 60, so the confirmation uses the 145 evaluation movements with
  the second-use caveat (decision 5, R52).

## Step 2: P trained (2026-10-15)

- `model/idiom.py`: 3.28M parameters (4 × 256, eight heads), 6,000 steps on GPU 1, 1,904 train parts
  (1.58M events).
- Log-likelihood per event: −18.1 at step 0, **train −3.75, dev −3.91** at the end (no overfitting).
- **Calibration** (real dev parts, 64-event windows): violin μ −3.87, σ 1.23 (1,643 windows); viola −3.96,
  1.30 (716); cello −3.88, 1.37 (587).
- Deviation (R52): sub-beat position instead of metre position.

## Corrections to Step 4 before any run (R53)

- **Retention floors on top and bass only.** The inner floor (0.83 trio) predates the S2 targets, which drop
  inner voices by the user's choice; in a smoke run from control-S2 it cost about −1.1 per window and
  would push RL to restore them.
- **Rollouts** keep the Block 4 decode order; melody-first is used for dev selection and confirmation.
- **"Detectors in range"** = criterion B's anti-hack items (repeat share ≤ v2b's; mean duration ratio ≥
  base − 0.05).
- **Contexts** from the RL base's own greedy decodes (R52).
- Smoke run (2 steps, MI05 from control-S2): window z −1.2 on average, term −0.46.

## Step 1c and Step 3 results (dev split, 2026-10-15 19:45)

**Step 1c, double stops per 100 notes (dev, masked, melody-first):** control-S2b trio violin 0.58 / viola
**2.31** (control-S2 4.44) / cello 2.00; duo violin 0.25 / cello 1.77. Drop rate 0.186 (S2 0.180). The base
decision (melody check) is made by stage B (`select_base.json`).

**Step 3, the gate: FAIL** (`model/results/idiom/gate_baseS2b.md`, `gate_baseS2.md`). Mean part z:

| slot | real | v2b | control-S2b | control-S2 | rl-AZ2 | restrike16 | up2oct | shuffle | dyads | AUC real>S2b | AUC S2b>v2b | min AUC v2b>hack |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trio violin | 0.04 | −1.44 | −0.11 | −0.13 | −0.74 | **+0.48** | −4.06 | −7.93 | −1.37 | 0.56 | 0.89 | 0.03 |
| trio viola | 0.06 | −1.70 | −0.72 | −0.79 | −1.12 | **+0.70** | −2.89 | −7.50 | −1.78 | 0.76 | 0.79 | 0.02 |
| trio cello | 0.04 | −0.56 | −0.57 | −0.48 | −0.57 | **+1.31** | −1.87 | −7.59 | −0.95 | 0.73 | 0.49 | 0.03 |
| duo violin | 0.04 | −1.67 | −0.16 | −0.14 | −1.32 | **+0.32** | −4.24 | −7.37 | −1.45 | 0.58 | 0.91 | 0.04 |
| duo cello | 0.08 | −2.42 | −0.64 | −0.61 | −1.89 | **+0.41** | −3.25 | −6.87 | −2.07 | 0.78 | 0.95 | 0.01 |

**Why it fails:**
1. **The re-strike hack scores above real parts in every slot.** Per-head log-likelihood (trio violin, 30 dev
   movements): restrike16 interval −1.06 and duration −0.11, against real −1.52 and −0.67. 95% of its events
   are 16ths (real 29%) and 64% repeat the previous pitch (real 14%). A per-event likelihood rewards
   predictable, repetitive streams: "typical" and "probable" are not the same thing. RL would find this
   (rl-AZ2 found the same hack against reward A).
2. **Real vs control-S2(b) is close** in the violin (AUC 0.56–0.58): S2's violin lines are already near
   real-part likelihood (per-head sum −4.08 against real −3.79).
3. **control-S2b vs v2b does not separate in the trio cello** (AUC 0.49): v2b's cello is already near S2b's.
4. Everything else ranks as intended: the other four hacks (an octave shift, shuffled parts, dyads, rl-AZ2) sit
   well below; v2b is far below real in every slot, and almost all of v2b's deficit is in the voices and
   double-stop heads (−0.52, −1.12 against real −0.04, −0.07), which S2 already fixed.

**Consequence (pre-registered):** no RL with P. Step 5 confirms the base (control-S2b if Step 1c holds)
against criterion B only.

**Proposal for a P v2 (not run; needs the user, since it is designed after seeing the gate):**
- score typicality two-sidedly: |z| rather than z (too predictable is also atypical);
- add a part-level distribution term: the distance between the part's histograms of duration, interval, voices
  and re-strikes and the real parts' histograms for that instrument (catches 95% 16ths directly);
- or train a discriminator (real parts against model outputs plus generated hack families).
Any v2 needs a new gate with hacks not seen while designing it.

## Step 1c decision (stage B, 20:02)

control-S2b **replaces** control-S2 as the base: dev viola double stops fall (4.44 → 2.31) and dev melody
retention by duration is unchanged (trio 0.988 against 0.988; duo 0.948 against 0.948).

## Step 5: confirmatory result (2026-10-15 20:31; `model/results/confirm5/CONFIRM5.md`)

The gate failed (R55), so as the brief specifies, **control-S2b alone is confirmed against criterion B**
(v2b masked as reference). 145 evaluation movements; **second use of this set** (R46 first).

| control-S2b vs v2b | Trio | Duo |
|---|---|---|
| **Criterion B** | **Fails item 1, on the cello:** 1.9 [1.4, 2.7] against 2.5. Viola now **2.5 [2.2, 2.9]** (S2: 5.2), violin 0.7. Items 2–4 hold. | **Holds** (all four) |
| Melody retention (count) | 0.995 (+0.028) | 0.973 (+0.020) |
| Interventions | 0.012 (−0.102) | 0.011 (−0.209) |
| Inner retention / harmony | 0.551 / 0.943 | 0.030 / 0.857 |
| Mean idiomatic z (P, descriptive) | −0.65 (v2b −1.46) | −0.53 (v2b −2.32) |

**Reading:**
- **The stricter viola rule worked:** the trio viola fell from 5.2 to 2.5 double stops per 100 notes, half the
  real-viola rate, with the melody and everything else unchanged.
- **The trio still fails item 1, on the cello's upper bound** (point estimate 1.9 below the real 2.5). The cello's
  double stops are the source cello's own: 2,089 in the output against 3,229 in the source cello parts of these
  movements, a quarter of them from two movements (Kalliwoda Op. 90/iv: 318 output, 417 source; Moeran iii: 204, 241).
  The real cello rate on these 145 movements is 3.21 per 100, so control-S2b plays fewer than the composers wrote.
  The frozen criterion uses the train-split rate (2.5); the result stands as a failure.
- **Correction to R47:** control-S2's cello also exceeded the bound in R46 (2.1 [1.5, 2.8]); R47 reported only the viola.
- Idiomatic z is reported only descriptively (P failed its gate).

## R58: control-S2c, the middle viola setting (dev split, 2026-10-16)

Viola gap 1 quarter (targets 5.28 per 100). Dev split, masked, melody-first:

| | control-S2 | **control-S2c** | control-S2b | real parts (train) |
|---|---|---|---|---|
| trio viola DS per 100 notes | 4.44 | **3.40** | 2.31 | 5.1 |
| trio violin / cello | 0.60 / 2.17 | 0.72 / 2.10 | 0.58 / 2.00 | 4.1 / 2.5 |
| duo violin / cello | 0.19 / 1.90 | 0.24 / 1.77 | 0.25 / 1.77 | — |
| melody retention, duration (trio / duo) | 0.988 / 0.948 | 0.988 / 0.947 | 0.988 / 0.948 | |
| interventions (trio / duo) | 0.015 / 0.012 | 0.015 / 0.013 | 0.014 / 0.012 | |
| inner retention (trio) | 0.548 | 0.563 | 0.553 | |

control-S2c lands midway, with everything else unchanged. No confirmatory test (third use of the evaluation
set needs the user). Listening excerpts: `decoding/results/examples/S2-vs-S2b-{trio,duo}/`, file `6_control-S2c_masked_*`.
