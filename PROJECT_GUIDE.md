# Project guide: playable string reductions (reduction_ladder, branch `headroom`)

This is a map of the project as of 2026-10-15. It covers:
1. what the system does;
2. how the pieces connect;
3. what each directory and file holds;
4. what every folder under `decoding/` means;
5. everything encountered in the last few days (Blocks 3–4, 2026-10-12 to 10-15).

The authoritative records stay where they are, and this guide points to them:
- **PROGRESS.md:** a dated log of every action and incident.
- **REVIEW.md:** every decision, numbered R1–R46.
- **BLOCK4.md / MODEL.md / DECODING.md:** results.
- **METRICS.md / UNSOURCED.md:** metric definitions and placeholder thresholds.

---

## 1. What the project does

**Goal:** arrange a string quartet for fewer instruments (string trio: violin, viola, cello; or
duo: violin, cello) so that the result is **playable** and stays **faithful and idiomatic**. The
thesis question is whether a model can *internalise* playing constraints rather than having
violations clipped afterwards.

**Pipeline:**

```
 OpenScore quartets (MusicXML)
        │  arrangement/parse.py, corpus.py, headroom/sources.py
        ▼
 note lists (part, onset, duration, pitch)  ──────────────┐
        │                                                  │
        │  training targets (model/augment.py, diagnose.py,│
        │  targets_s2.py): "the correct trio" per window   │
        ▼                                                  │
 ARRANGER MODEL (model/net.py, 4.9M-parameter transformer) │
   per source note: part (or DROP) × octave × realisation  │
        │  trained by model/train.py (supervised),         │
        │  train_s.py (supervised on S/S2 targets),        │
        │  grpo.py (reinforcement learning)                │
        ▼                                                  │
 DECODER (model/decode.py)  ◄── CHECKER as a MASK          │
   commits notes pass by pass;     (arrangement/checker,   │
   every choice is checked;         GrowingChecker in      │
   a blocked choice falls back      arrangement/decode)    │
   to the next one, finally DROP                           │
        ▼                                                  │
 arrangement records (.jsonl) ─────────────────────────────┤
        │                                                  ▼
        │                       HARNESS (arrangement/eval/harness.py)
        │                       playability (checker), fidelity vs source,
        │                       texture, reduction metrics
        ▼                                  ▼
 RENDERER (decoding/render_excerpts.py)    evaluation scripts
 MusicXML / PDF / PNG for review           (model/evaluate.py, eval_rl.py, confirm_eval.py)
```

**Baselines** go through the same harness:
- **Ou et al.,** a published neural arranger, generated with and without the checker mask (decoding/);
- **continuity / naive,** rule-based assigners;
- **AMT,** secondary, generation only;
- **control,** random assignment;
- **Ou + repair,** deterministic re-routing.

---

## 2. Key concepts and vocabulary

| Term | Meaning |
|---|---|
| **Checker** | The hard playing rules (`arrangement/checker`, thresholds in `arrangement/config/instruments.yaml`). Versioned and tagged in git: `checker-v1` … **`checker-v5`** (current). It is never changed silently; each change gets a new tag and a re-run of the baselines. |
| **Mask / masked** | The checker used during decoding: before a note is committed, the decoder asks the checker whether that choice breaks a rule. If it does, the choice is masked out and the next is tried, finally DROP. A *masked* output therefore has 0 violations by construction. *Unmasked* = the model's raw choices. |
| **Intervention** | A note whose top choice the mask had to block. The **intervention rate** measures how much the model relies on the mask; a low rate means the constraint is internalised. |
| **D** | Violations per 100 notes for the worst check type (playability). |
| **Decode v1 / v2 / v3** | Decoder versions. **v2:** unison duplicates in one part are merged (R37). **v3 (melody-first):** within each pass, notes are committed by voice tier (melody, then bass, then inner) so a held melody note wins conflicts (R42). |
| **Voice tier** | Per source note, by sounding pitch: *top* (nothing higher sounding), *bass* (nothing lower), *inner* (the rest). |
| **Retention** | Share of source notes reproduced (pitch and onset within a 16th, any part). It is reported per tier, and by duration where stated. |
| **Unneeded double stop** | Two or more notes sounding in one output part whose pitches don't sound together in a single source part. |
| **Target** | The "correct answer" shown in supervised training. There are no human trio arrangements, so targets are built by rule. **Literal reduction** (v1/v2b): Vn1+Vn2 → violin, so full of merged double stops. **Oracle-under-mask** (control S): the literal reduction made playable. **S2** (R44): double stops resolved in your priority order (keep the melody, move or re-voice or drop inner voices). |
| **GRPO** | Group Relative Policy Optimization, the RL method (`model/grpo.py`): sample 8 arrangements of a window, score them, nudge the model towards the above-average ones, with clipping and a KL anchor. |
| **Reward settings** | A, B, C (BLOCK4 2b), A2 (duration-held rule), A3 (λ = 3), M2 / M3 (duration-weighted, relocation credit). See BLOCK4.md and REVIEW R31–R41. |
| **Gate** | The pre-registered test in DECODING.md: does masking cost Ou et al. fidelity (outcome 1 = no; 2/3 = yes, so learning has a target)? |
| **Dev split / evaluation set** | 476 train, 61 dev (selection and validation), 150 evaluation movements (never trained on; confirmatory tests only). The 5 review movements (022, 067, 039, 042, 148) are in the evaluation set and are excluded from the confirmatory test because you have listened to them. |

---

## 3. Directory structure

### Top-level documents

| File | What it is |
|---|---|
| `DECISION.md` | The pre-registered headroom decision rule (Block 1–2). |
| `HEADROOM.md` | Headroom measurement results: how unplayable existing systems are. |
| `DECODING.md` | The gate: masked Ou et al., with amendments A1–A4 (checker v2–v5) and the results of each. |
| `METRICS.md` | Metric definitions and changelog. Current version: **1.5.0-draft**. |
| `MODEL.md` | Block 3: arranger-v1 (architecture, training, evaluation). |
| `BLOCK3_HANDOFF.md` | Handoff from Block 3 to Block 4. |
| `BLOCK4.md` | Block 4 brief (approved) and all its results, in order. |
| `REVIEW.md` | Every decision taken (R1–R46), with reasons. |
| `UNSOURCED.md` | Placeholder thresholds U1–U20 and where each came from. |
| **`PROGRESS.md`** | Dated log of all actions and incidents (since 2026-10-13, backfilled to 10-12). |
| `PROJECT_GUIDE.md` | This file. |
| `PLAN.md`, `NOTES.md`, `BUILD_PLAN.md` | Earlier planning notes (pre-pivot). |
| `reduce*.py`, `diagnostics*.py`, `salience.py`, … | The **legacy** reduction-ladder code from before the pivot. Untouched. |

### `arrangement/`: the verification layer (checker, evaluation, instruments)

| Path | What it does |
|---|---|
| `instruments.py` | Instrument definitions (ranges, strings, hand position, thresholds), loaded from `config/instruments.yaml`. |
| `config/instruments.yaml` | Checker thresholds per instrument. Every unsourced value is marked PLACEHOLDER (Uxx). |
| `checker/batch.py` | The checker: all rules over a whole arrangement. |
| `checker/incremental.py` | The same rules, updated note by note (commit/uncommit). Tested to agree with batch. |
| `checker/rules_v2.py` | Shared rule helpers (string placement, stretch, shifts). |
| `checker/types.py` | Violation types; `CHECKS` lists every rule, v1 to v5. |
| `decode/growing.py` | `GrowingChecker`: the incremental checker for notes created on the fly. Used by every masked decoder. |
| `eval/harness.py` | The evaluation harness: records → metrics.jsonl / csv. |
| `eval/playability.py`, `fidelity.py`, `texture.py` | Playability, fidelity vs source, and texture metrics. |
| `eval/reduction.py` | **Block 4:** retention per voice tier, weighted fidelity, unneeded double stops (METRICS 6b). |
| `eval/record.py` | The arrangement record format (system, source, output notes, bars). |
| `assign.py` | Rule-based assigners (continuity, naive). |
| `parse.py`, `corpus.py`, `ties.py`, `strip.py` | MusicXML parsing and the corpus. |

### `headroom/`: Block 1–2 measurement

| Path | What it does |
|---|---|
| `sources.py` | Builds the 150 evaluation sources (`headroom/data/sources/NNN.json`). |
| `run_models.py`, `generate.sh` | Runs Ou et al. and AMT unconstrained. |
| `to_records.py`, `measure.py`, `report.py`, `figure.py` | Conversion to records, the headroom measurement, the report and the figure. |
| `data/out/<system>/<regime>/NNN.json` | Raw system outputs. Older checker versions are kept as `ou_band_masked_checker-vN`. |
| `data/records/<system>__<regime>.jsonl` | Arrangement records for every baseline. Older checker versions are kept as `*_checker-vN__…`. |

### `decoding/`: constrained Ou et al. (the gate) and score rendering

**Scripts:**

| Script | What it does |
|---|---|
| `run_constrained.py` | Masked decoding of Ou et al.: the REMI-z logits processor plus the checker. |
| `generate.sh`, `generate_v5.sh` | Run it for one regime in shards (v5: GPU 1 only). |
| `gate.py` | The pre-registered gate (DECODING.md): masked against unconstrained, with paired bootstrap. |
| `repair.py` | The Ou + repair baseline (deterministic re-route, then octave, then drop). |
| `run_v2.sh` … `run_v5.sh` | The full re-run chain for each checker version (amendments A1–A4). |
| `render_excerpts.py` | **Score rendering for review:** exact-rhythm MusicXML with violation marks (red letters), triple stops (orange "3"), string instruments declared (so MuseScore plays strings), and unison duplicates drawn as one note. Options: `--model-run`, `--regime trio\|duo`, `--oracle`. |
| `to_pdf.py` | MusicXML → PDF and PNG (Verovio). |
| `render_masked.py` | Legacy renderer (superseded). |

**`decoding/results/`:**

| Folder | What it holds |
|---|---|
| `trio/`, `duo/` (+ `*_gate.log`) | The **original checker-v1 gate** (2026-10-08): `gate.json` plus harness rows. |
| `v2/`, `v3/`, `v4/`, `v5/` | The gate re-run under each checker version (DECODING.md A1–A4). One subfolder per regime (trio, duo, solo_violin, solo_flute, piano), each with `gate.json` and `harness/`. **v5 is current.** |
| `examples/` | Review scores. Each `<idx>_bars<a-b>/` folder holds `0_source_quartet`, `1_ou_unconstrained_*`, `2_ou_masked_*`, `3_arranger_*` (unmasked), `4_arranger_masked_*`, optionally `5_oracle_under_mask_*`, plus `README.txt` (legend and note counts), each as .musicxml/.pdf/.png. |

**`examples/` subfolders:**

| Subfolder | Contents |
|---|---|
| `067_bars1-16`, `…_checker-v2`, `…_checker-v3` | Early Haydn excerpts of Ou et al. under checker v1–v3. |
| `review_checker-v4-draft`, `checker-v4` | Your checker-v4 review excerpts. |
| `arranger-v1` | Block 3 model. |
| `arranger-v2b`, `review1-trio`, `review1-duo` | The RL starting model, with the oracle under the mask. |
| `rl-A-*`, `rl-SA-*`, `rl-AZ2-trio`, `rl-SA2Z-trio`, `rl-SA3Z-trio`, `rl-SM2Z-melodyfirst-trio` | Successive RL runs (rl-AZ2 is the repeat-splitting hack). |
| `s2-target-trio` | The S2 *training target* (rule output, not a model). |
| **`control-S2-trio`, `control-S2-duo`** | **The current best model.** `022_bars60-75/DIFFERENCES.md` gives the bar-by-bar comparison with Bridge's quartet. |

### `model/`: the arranger, training, RL and evaluation

**Model and supervised training:**

| File | What it does |
|---|---|
| `net.py` | The transformer: per note, a part head (part tokens + DROP), an octave head and a realisation head. `src_feature` flag for v2. |
| `features.py` | Encoding of a window (pitch, time, committed labels) for the network. |
| `augment.py` | Training examples: target reduction, realisation labels, `expand()` (labels → notes), `INote`. |
| `train.py`, `config*.yaml` | Supervised training (arranger-v1, v2, v2b). |
| `train_s.py` | Supervised fine-tuning on fixed targets: `--targets oracle` (control S) or `s2` (control-S2). |
| `targets_s2.py` | **The S2 target builder** (R44/R45, including the cello 6th-position rule U20). |

**Decoding:**

| File | What it does |
|---|---|
| `decode.py` | The decoder: windows, passes, mask fallback, unison merge (v2), `--melody-first` (v3), `--out-dir`. |

**Reinforcement learning:**

| File | What it does |
|---|---|
| `grpo.py` | **GRPO:** rollouts (`RolloutState`), candidate masks recorded and replayed, reward (`window_reward`, `kept_weights`), loss (PPO clip, KL, feasibility term), the lockstep engine (batched GPU forwards), the training loop, validation. |

**Evaluation and diagnostics:**

| File | What it does |
|---|---|
| `evaluate.py` | Block 3 Step 5 evaluation. |
| `compare_runs.py` | v2 / v2b against v1. |
| `eval_rl.py` | Block 4 criterion 2g and detector ranges. |
| `confirm_eval.py` | **The confirmatory test (R46).** |
| `diagnose.py` | Block 4 Step 1: oracle under the mask, double-stop provenance, interventions. |
| `rerun_baselines.py` | METRICS 1.4.0 re-score of every baseline. |
| `dev_decode_compare.py` | Decode v2 against v3 on the dev split. |
| `double_stop_stats.py` | Double stops per part against real quartets. |
| `val_checkpoint.py` | Dev validation of a saved checkpoint. |
| `profile_decode.py` | Compute profile. |

**Launch scripts:** `run_*.sh`, `decode_eval*.sh`, `snapshot_eval.sh`, `run_confirm.sh`.

**Data and results:**

| Path | Contents |
|---|---|
| `data/` | `train.jsonl` (476), `val.jsonl` (61), `split.json`. |
| `results/arranger-v1`, `v2`, `v2b` | Checkpoints, logs, records (`records_dv1/` holds the decode-v1 records). |
| `results/rl/<run>/` | Every RL and control run: `checkpoint.pt`, `log.csv` (training and validation), `config.json`, `records/`, `eval_*.md/json`. Also `contexts/` (window contexts and oracle labels), `targets_s2__train.pkl`, `detector_ranges*.json`. |
| `results/metrics-1.4.0/<regime>/` | All baselines re-scored under 1.4.0 (`dv1/` = before decode v2). |
| `results/diagnostics/` | Step 1 diagnostics. |
| `results/confirm/` | **The confirmatory test** (records, `eval.json`, `CONFIRM.md`). |
| `logs/` | Every job log, including `rl_chain.log`, the timeline of all chains. |
| `wandb/` | Offline Weights & Biases runs. Sync with `wandb sync model/wandb/offline-run-*`. |

### `tests/`

Checker tests: `test_checker_v2…v5.py`, `test_checker_incremental.py`, `test_decode_growing.py`; batch, incremental and growing must agree. The rest:
- `test_eval_reduction.py`: the 1.4.0 metrics;
- `test_grpo.py`: masking-ratio identity, replay, sampling, masked-out candidates, the mask-unaware bug, micro-batch equivalence, lockstep = sequential;
- `test_decode_unison.py`: decode v2;
- `test_model_v2.py`, `test_model_augment.py`.

The full suite runs with `.venv/bin/python -m pytest`. The torch tests run in
`/scratch/ashleyz/headroom_models/env_train` (it has no pytest; a small runner was used).

**Environments:**
- `.venv`: the checker and harness;
- `env_train`: torch and the model;
- `env_m2m`: Ou et al.

---

## 4. How the components attach

- **Checker → everything.** One rule implementation (batch and incremental, tested equal) is used:
  - as the **mask** inside every decoder: Ou et al. (`run_constrained.py`), the arranger
    (`model/decode.py`), the oracle and S2 target builders, and GRPO rollouts;
  - as the **playability metric** in the harness;
  - as the **renderer's** red marks.

  So "playable" means the same thing everywhere.
- **Records are the contract.** Every system, whether model, baseline or oracle, emits
  `ArrangementRecord`s. The harness, the evaluation scripts and the renderer read only records.
- **Targets → supervised model → decoder → records.** The target sets the model's habits. The
  decoder (with the mask) makes the output playable. Records are scored.
- **RL loop (`grpo.py`).** Each rollout runs the same decoder logic (`RolloutState`, with the
  Committer as mask). The reward reads the rollout's output notes against the source. Masks are
  recorded and replayed in the update, so the policy ratio is exact.
- **Versioning.** The checker (tags), METRICS (version string), decode (v1–v3) and runs (names) are
  all versioned. Older outputs are kept, never overwritten (`*_checker-vN`, `records_dv1`, `dv1/`,
  `eval_*_dv1.*`).

---

## 5. What we encountered in the last few days (2026-10-12 to 10-15)

Chronological, with the decision numbers in REVIEW.md.

### Block 3 (model), 10-12

1. **checker-v4** from your MuseScore review: the held-note rule, restrike, and fast double stops.
2. **Ou et al. + repair** added as a baseline.
3. **arranger-v1** trained (supervised).
   - Several decoder bugs were fixed along the way.
   - Masked, it beats every playable Ou et al. variant on fidelity.
   - It is written up in MODEL.md.

### Block 4 setup (10-12/13)

4. **Step 1 diagnostics.**
   - **Intervention figures corrected:** the intervention rate is 11.9% / 22.2%. The 24% / 51% in
     MODEL.md came from a failed-options counter and has been corrected.
   - **The targets themselves are infeasible:** for 15–25% of notes. The ceiling comes mostly from
     merging parts, not from checker imperfection (a quartet loses only 0.7% of its notes).
   - **Double stops come from merging:** 92–97% of them.
5. **BLOCK4.md approved;** you delegated the tier rule (R28).
6. **arranger-v2:** the source-part feature made the part head a lookup that lost the melody.
   **v2b** (class weights only) became the RL starting point (R29, R30).
7. **METRICS 1.4.0** (reduction metrics), all baselines re-scored, detector ranges fixed before any
   RL run.
8. **GRPO built.**
   - **Tests:** five masking-ratio tests.
   - **Incidents:**
     - context precompute rewritten for CPU;
     - a `pgrep` self-kill;
     - two GPU out-of-memory crashes, fixed by micro-batching (R31, R32).
   - Later, the **lockstep engine:** 3–6× faster, with network forwards moved onto the GPU.

### Block 4 runs (10-13)

9. **Control S** (supervised on feasible targets) cut interventions by 62–77% with no RL.
10. **rl-A, rl-C** (pre-registered): fidelity went up but interventions didn't fall. rl-C found a
    reward hack (splitting held notes into repeats), and the detectors caught it.
11. **Diagnosis (R34):** under a permanent mask, the RL objective gives no gradient to infeasible
    choices. The fix is a feasibility term. Its first version made the model drop 60% of notes; the
    conditional version (rl-AZ2) found the repeat-splitting hack (R36).
12. **Your review: same-note chords** led to **decode v2** (unisons merged) and a full re-decode of
    every model (R37).
13. **λ sweep (R38):** λ = 3 cuts double stops, but by dropping notes. **Evaluation-set tuning
    flagged (R39):** R33–R38 are development results only.
14. **Your Bridge review:**
    - **strings sounded like piano in MuseScore:** fixed in the renderer;
    - **held melody notes were being lost:** reward M (R40) weights by duration and gives relocation
      credit; neither M run passed the dev selection (R41);
    - **melody-first decoding (decode v3, R42)** fixed bar 70.

### Checker-v5 and S2 (10-14/15)

15. **checker-v5 (R43):** triple stops in normal hand position, plus `triple_recover`. All
    baselines were re-run overnight on GPU 1; the gate is unchanged (outcome 2/3).
16. **"Too many double stops"** (your key complaint):
    - **Real parts:** 2–6 double stops per 100 notes. **Our models:** 15–26.
    - **Your direction:** fix it in training, not at inference.
    - **S2 targets (R44):** melody first; move or re-voice or drop inner voices rather than
      double-stop them; cello moves stay below 6th position (U20).
    - **You approved the style (R45).**
17. **control-S2:**
    - double stops at real-quartet levels (violin 0.6 per 100 notes);
    - melody kept (99% by count, 95–99% by duration);
    - the checker barely intervenes (1–1.5%);
    - inner voices dropped (18% trio, 41% duo).

    **Bridge 60–75:** the full melody with held notes, Vn2 moved to the viola, Bridge's viola line
    mostly dropped (`control-S2-trio/022_bars60-75/DIFFERENCES.md`).
18. **The confirmatory test (R46),** frozen before decoding: control-S2 against v2b (and S), checker
    v5, melody-first decoding, 145 evaluation movements. Criterion A (the original 2g) and
    criterion B (your stated priorities). Running.

### Lessons recorded

- **Preservation-only objectives produce whack-a-mole.** The model keeps finding the next loophole:
  double stops, then repeats, then drops. The long-term fix is a learned "idiomatic part" term.
- **Design choices made by looking at evaluation-set results contaminate the test.** Select on the
  dev split and freeze before confirming.
- **Commit order in decoding matters musically,** hence melody-first.

---

## 6. Files written in the last few days, and what is in them

### Documents

| File | Contents |
|---|---|
| `BLOCK4.md` | The approved brief, plus results sections for every step and run. |
| `PROGRESS.md` | The running log. |
| `PROJECT_GUIDE.md` | This guide. |
| `REVIEW.md` | R28–R46 added. |
| `DECODING.md` | A3 and A4 results added. |
| `METRICS.md` | Section 6b, plus changelog 1.4.0 and 1.5.0. |
| `UNSOURCED.md` | U15 changed; U19 and U20 added. |
| `MODEL.md`, `BLOCK3_HANDOFF.md` | Intervention-rate correction. |

### Checker and evaluation (`arrangement/`)

| File | Changes |
|---|---|
| `eval/reduction.py` | New file: the reduction metrics. |
| `checker/batch.py`, `checker/incremental.py`, `checker/types.py`, `instruments.py`, `config/instruments.yaml` | The checker-v5 rules. |
| `eval/harness.py` | METRICS 1.5.0-draft; the reduction section added. |
| `eval/playability.py` | Applies-map for the new checks. |

### Model (`model/`)

| Status | Files |
|---|---|
| **New** | `diagnose.py`, `profile_decode.py`, `compare_runs.py`, `rerun_baselines.py`, `grpo.py`, `train_s.py`, `eval_rl.py`, `targets_s2.py`, `dev_decode_compare.py`, `double_stop_stats.py`, `val_checkpoint.py`, `confirm_eval.py`, `config_v2.yaml`, `config_v2b.yaml`, and all `run_*.sh`. |
| **Changed** | `augment.py` (src and merged fields), `features.py`, `net.py` (src feature), `train.py` (class weights), `decode.py` (intervention counter, unison merge, melody-first, out-dir). |

### Decoding and rendering

| File | Changes |
|---|---|
| `decoding/render_excerpts.py` | `--model-run`, `--regime`, `--oracle`, unison merge for display, string instruments, the `triple_recover` legend. |
| `decoding/run_v5.sh`, `decoding/generate_v5.sh` | New: the checker-v5 re-run. |

### Tests

New: `test_eval_reduction.py`, `test_grpo.py`, `test_decode_unison.py`, `test_model_v2.py`,
`test_checker_v5.py`. Updated: `test_checker_v3.py`.

---

## 7. Current state and next steps

- **Running:** the confirmatory test (`model/run_confirm.sh` → `model/results/confirm/CONFIRM.md`).
- **Open questions for you:**
  - Is G4 the right ceiling for moved cello notes (U20)?
  - Cello triple stops: normal (3) or extended (4) position?
  - The large files in git history (`9ffb283`): leave, or rewrite?
- **After the confirmatory test:**
  - write up Block 4;
  - a **Block 5 brief** from you. My suggestion: the learned idiomatic-part reward, and RL from
    control-S2.
