# METRICS — evaluation specification

**Version 1.3.0-draft.** Status: **DRAFT, awaiting approval.** On approval the version becomes
1.0.0 and this file is frozen. From then on any change bumps the version and adds a dated entry to
the changelog at the bottom saying what changed and why. Every metric output carries
`metrics_version` (`arrangement/eval/harness.py: METRICS_VERSION`), so runs under different versions
are never silently mixed.

Written before any model, reward or training exists. Metrics chosen after seeing results are not
credible, so they are fixed here first.

**Never aggregated.** Playability, fidelity, texture and soft cost are separate sections of every
output. No section is combined with another, and within playability the check types are never summed.
The trade-off between playability and fidelity *is* the result: a single score would hide it.

Implementation: `arrangement/eval/` (record, harness, fidelity, playability, texture) and
`arrangement/soft/`. Known-answer tests: `tests/test_eval_harness.py`, `tests/test_soft.py`.

---

## 1. Arrangement record (the only input)

Every system (rule-based assigner, constrained decoding, trained model, external system) emits one
record per (input, seed). The harness reads nothing else. Format: JSON Lines, one record per line
(`arrangement/eval/record.py`, `record_version` "1").

| Field | Required | Meaning |
|---|---|---|
| `system`, `system_version` | yes | system identifier and free-form version string |
| `seed` | yes (null if deterministic) | sampling seed |
| `input_id` | yes | identifies the source. Records sharing an `input_id` share one source: the seed groups. |
| `ensemble` | yes | ensemble name (informational; the instruments come from `output.parts`) |
| `source` | yes | the score being arranged: parts `[{name, instrument}]` and notes |
| `output` | yes | the arrangement: parts = the target ensemble in part-index order, and notes |
| `bars` | yes | source bar timeline `[[start, length], ...]`. Defines the segments. |
| `assignment` | no | the assignment decisions: `assignment[i]` = output part of source note `i`, −1 = dropped. Only systems that place source notes (assigners, constrained decoding) have it. If present it must reproduce `output.notes` exactly (checked on load). |
| `reference` | no | a human arrangement for the same task, if one exists |
| `reference_source_parts` | no | for each output part, the source parts it reduces. Used for per-part note-count and duration ratios. |
| `window` | no | `[start, end)`, when the system covered only part of the source (e.g. AMT's 32 bars) |
| `meta` | no | free-form, never read by any metric |

A note is `[part, onset, duration, pitch]`:
- times are exact quarter-note fractions written as strings (`"3/2"`);
- pitch is sounding MIDI;
- duration 0 marks a grace note.

**Why the output is notes, not assignment decisions.** Generative systems (Ou et al., AMT, most trained
models) write new notes rather than placing source notes. The output is therefore always explicit,
and `assignment` is optional provenance. Every metric reads `output`. None reads `assignment`.

The ensemble's instrument definitions are the frozen hard-tier config (`arrangement/config/`, tag
`checker-v1.1`). `run.json` records the SHA-1 of every config file used.

---

## 2. What each metric needs

The paper relies on this distinction. Every fidelity metric of the published framework needs a
target to compare against. **Violation rate needs neither a reference nor a source nor a listener:**
it is computable on a single arrangement in isolation. That is the structural reason it adds
something the published framework cannot measure.

| Metric | Needs a reference arrangement | Needs only the source | Needs neither |
|---|:-:|:-:|:-:|
| Hard violations per 100 notes, per check type | | | ✔ |
| Soft-tier cost, per cost type | | | ✔ |
| Note F1, Note_i F1, Mel F1, I-IoU **vs reference** | ✔ | | |
| Note F1, Note_i F1, Mel F1, I-IoU **vs source** (Ou et al.'s own reconstruction protocol) | | ✔ | |
| Top-voice melody F1 (addition) | ✔ (vs reference) | ✔ (vs source) | |
| Harmonic agreement per beat (addition) | | ✔ | |
| Polyphony rate | | | ✔ |
| Note density | | | ✔ |
| Rhythmic independence between parts | | | ✔ |
| Variance across seeds | | | ✔ (needs ≥ 2 seeds of one input) |
| Note count against source, per part | | ✔ | |
| Pitch variance; distance from range edges | | | ✔ |
| Mean duration against source | | ✔ | |
| Doubling rate against source | | ✔ | |
| Near-limit distribution (verifier gaming) | | | ✔ |

"Neither" metrics are also reported for the source (`__source` fields) when the source is present.
That is for comparison only: they don't need it.

---

## 3. Playability (hard tier)

From the frozen checker (`arrangement.checker.check`, tag `checker-v4` since metrics 1.3.0), unchanged. For each check
type c ∈ {simultaneity, range, chord_size, hand_span, transition, multistop, bow, shift, duplicate, hand_leap,
triple_onset, triple_stretch, triple_rate, double_onset, restrike, double_rate}:

- `c__violations`: count; `c__per_100` = 100 · count / output notes;
- `c__implicated_per_100` = 100 · distinct notes in a violation of type c / output notes;
- `c__applies`: whether any instrument of the ensemble has that check (e.g. simultaneity only
  for monophonic instruments). A rate of 0 where the check does not apply is 0 by construction.

`by_check_part` counts violations per (check type, part). An empty output gives `per_100` = null,
not 0. **Pooling across records:** Σ violations / Σ notes × 100, per check type. Check types are
never summed. Rule definitions are in `arrangement/checker/incremental.py`; thresholds and their
sources are in `arrangement/config/instruments.yaml` and UNSOURCED.md.

## 4. Soft tier (provisional)

Reported only under `soft` and never folded into playability or any other number. Per cost type
(breath, bow, shift, crossing, register, key, repeated): `__applies`, `__cost`, `__events`,
`__per_100`, and per part. Cost types are never summed. Thresholds live in
`arrangement/config/soft.yaml`, which carries `soft_version` and `config_sha1`. Every one is a
placeholder (UNSOURCED.md S1–S9) until the performer study calibrates it. The soft tier has its own
version, so recalibrating it does not change this spec's version. Re-running only the soft section:
`python -m arrangement.soft RECORDS.jsonl --config X.yaml --out DIR`.

---

## 5. Fidelity

### 5.1 Adopted from Ou et al., as published

Source of truth: L. Ou, J. Zhao, Z. Wang, G. Xia, Q. Liang, T. Hopkins, Y. Wang, "Unifying Symbolic
Music Arrangement: Track-Aware Reconstruction and Structured Tokenization", arXiv:2408.15176
**v5** (earlier versions were titled "Unifying Multitrack Music Arrangement…"), Section 4.3 and
Appendix C.1, equations 2–9. These are implemented from **the paper's equations**, not from the
released code (§5.4 lists where the two differ). They are not improved upon: comparability with the
published baseline matters more.

Notes are events e = (t, p): onset in quarter notes, sounding MIDI pitch. A note x matches y iff

  |t_x − t_y| < δ_t and p_x = p_y,  δ_t = one 16th note = 1/4 quarter  (eq. 2)

Precision = |M|/|X|, Recall = |M|/|Y|, F1 = 2PR/(P+R) (eq. 3–5), with X = output and Y = target.

| Metric | Definition |
|---|---|
| `note_f1` | the matching above (eq. 2–5) |
| `note_i_f1` | the same, with the additional condition i_x = i_y, i = instrument (eq. 6) |
| `mel_f1` | Note F1 between the melody tracks of output and target. Melody track = the track (part) with the highest mean pitch, argmax over tracks of (1/\|T_i\|) Σ p_e (eq. 7–8), chosen separately in output and target |
| `i_iou` | \|I_out ∩ I_tgt\| / \|I_out ∪ I_tgt\|. An instrument is present if at least one of its notes occurs (eq. 9) |

"All objective metrics are calculated at the segment level, and arithmetically averaged across the
test set" (App. C). For band arrangement the segment is one bar (Section 3.2).

### 5.2 Decisions where the paper is silent (harness choices, recorded here)

1. **Segment = one bar of the source** (`bars`), assigned by onset: a note belongs to the bar
   containing its onset. Both output and target are cut on the source's bar lines.
2. **M is a maximum one-to-one matching.** The paper calls it "the set of matched note pairs". With
   one-to-one matching, an output that duplicates a note loses precision. Computed exactly, by a
   greedy two-pointer per (pitch[, instrument]), which is optimal for points on a line.
3. **Empty segments.** If X and Y are both empty, the segment is excluded from the mean (F1
   undefined). If exactly one is empty, F1 = 0. I-IoU follows the same rule.
4. **Melody track per segment.** The paper defines it on "a multitrack piece" while computing every
   metric per segment. It is chosen per segment. Ties go to the lower part index.
5. **Instrument = instrument type** (the config key: violin, viola, cello, flute, piano). This is
   the analogue of the paper's instrument token (a General MIDI program). **Consequence:** two parts
   of the same instrument type are indistinguishable to Note_i F1 and I-IoU, so Violin 1 and Violin 2
   of a quartet both count as "violin". This keeps the published definition. It means Note_i F1
   cannot detect swapping two violin lines.
6. **Reference or source with a different instrument count** (every reduction). No adaptation is
   needed: instruments are matched by type, so a quartet target's two violins form one "violin" pool
   against a trio's one violin. Instruments missing on either side lower Note_i F1 and I-IoU, which
   is the published behaviour. A solo-flute reduction of a quartet therefore scores Note_i F1 = 0 and
   I-IoU = 0 against the source by construction. Report it as "not comparable", not as poor fidelity.
7. **Grace notes** are note events and count in every F1.
8. **Window.** If the record has a `window`, source, reference and bars are restricted to it.

### 5.3 Two targets

- `fidelity.vs_source`: the target is the source itself. This is Ou et al.'s own evaluation
  protocol: their models reconstruct the original, which is the target. Always computed.
- `fidelity.vs_reference`: the target is a human arrangement for the same ensemble. Computed only
  when `reference` is present. Null otherwise, never imputed.

**Pooling.** Each metric also outputs `__sum` and `__n_segments`. The test-set value is
Σ sums / Σ n_segments over records. That is the paper's single mean over all segments, not a mean of
per-record means.

### 5.4 Known differences between the paper and the released code (`music2music_code @ 8359bbd`)

Recorded so that numbers can be reconciled. The paper wins (user decision, 2026-10-07).

| | Paper (implemented) | Released code `m2m/evaluate.py` |
|---|---|---|
| Note matching | \|Δt\| < one 16th, one-to-one | onsets quantized to a 16-cell grid per bar, the piano roll binarized, then sklearn `f1_score` (duplicates collapse; onsets past cell 15 are clipped into the last cell in bars longer than 4/4) |
| Mel F1 melody | every note of the highest-mean-pitch track | `top_note=True`: only the highest note per onset within that track |
| I-IoU target | instruments of the target | `calculate_inst_iou_from_condition`: the requested instrument set |
| Both segments empty | (silent) excluded | sklearn returns 0 |

The paper's Voice Error Rate (VER) is not adopted, because the brief lists the metrics to adopt.

### 5.5 Additions (ours; labelled as additions in every output and figure)

- **`mel_top_f1`: top-voice melody F1.** Note F1 (eq. 2–5) between the top voices of output and
  target. Top voice (skyline) of a segment: at each onset t, the highest non-grace note starting at
  t, kept unless a higher note is still sounding through t (onset < t < end). Unlike `mel_f1`, it
  follows the melody across parts.
- **`harmony`: harmonic agreement per beat against the source.** This is the quantity the reward
  will optimise. Beats are consecutive quarter notes from the start of the bars (or window). For
  each beat, a 12-bin pitch-class profile is built: each non-grace note adds its overlap with the
  beat, in quarter notes, to its pitch class. Agreement for a beat is the cosine similarity of the
  output and source profiles. Beats where the source is silent are excluded, and a beat where only
  the output is silent scores 0. `harmony` is the mean over beats, with `__sum` and `__n_beats` for
  pooling. It is octave- and voicing-invariant by design: it measures *which harmony*, not *which
  notes*.

---

## 6. Texture and diversity (the reward-hacking detectors)

These are implemented once (`arrangement/eval/texture.py`, `playability.near_limit`) and used both
as evaluation metrics and as reward-hacking detectors. Computed on the output; source values are
reported alongside under `__source`.

| Field | Definition |
|---|---|
| `polyphony_rate` | share of sounding time (union of non-grace note intervals) with ≥ 2 distinct pitches sounding. Also given per part. |
| `note_density` | notes per quarter note of covered source time (bar span or window). Total and per part. |
| `rhythmic_independence` | mean over pairs of non-empty parts of 1 − \|On_a ∩ On_b\| / \|On_a ∪ On_b\|, On = the part's set of onset times. 0 = every pair rhythmically locked; 1 = no shared onsets. Null with fewer than 2 non-empty parts. |
| `n_notes__per_part`, `note_ratio__total`, `note_ratio__per_part` | note counts. Total ratio = output notes / source notes. Per-part ratio = output part notes / notes of its `reference_source_parts` (null if those are not given) |
| `pitch_std__per_part` | standard deviation of pitch per part |
| `range_edge_distance__per_part` | per note, min(pitch − low, high − pitch) in semitones (negative = out of range). Mean, min, 5th percentile, share within 2 semitones. |
| `mean_duration`, `duration_ratio__total`, `duration_ratio__per_part` | mean non-grace duration, and its ratio to the source (total; per part against `reference_source_parts`) |
| `doubling_rate` (and `__source`) | share of non-grace notes for which another part has a note at the same onset with the same pitch class (unison or octave doubling) |
| `near_limit` | per check type, the slack (limit − measured) at every opportunity, not only at violations: range = edge distance per note; chord_size = max_chord − sounding notes per onset; hand_span = reach − best two-hand span per onset; transition = allowed − leap per transition; simultaneity (monophonic parts) = gap from release to next onset, in 16ths. Histogram over integer slack −5…5 (clipped), plus `share_at_limit` (0 ≤ slack ≤ 1) and `share_violating` (slack < 0). Computed with the frozen checker's own code, with the limit relaxed; for every check except simultaneity, the count of slack < 0 equals the checker's violation count (tested). |
| seeds (`seeds.jsonl`) | per (system, ensemble, input_id): mean and std across seeds of every numeric metric, and `pairwise_note_f1` / `pairwise_note_i_f1`, the mean over seed pairs of the paper's Note F1 and Note_i F1 between the two outputs. 1 = every seed gives the same arrangement. Groups with one seed get `spread` = null and pairwise = null. |

**Choice to review: "independent movement between parts" is rhythmic independence.** It is onset-set
disjointness: it flags lock-step texture, and it is defined for any instrument count. Directional
independence (contrary or oblique versus parallel motion between line pairs) is the other candidate.
It is not included in 1.0.0: it needs a line per part, which polyphonic parts don't have.

---

## 6b. Reduction metrics (added in 1.4.0-draft; `arrangement/eval/reduction.py`)

These measure what a reduction keeps, and the double stops it creates. They need no provenance and no
checker, so every system gets them. Field group: `reduction`.

| Field | Definition |
|---|---|
| `retention__top`, `__inner`, `__bass` (and `__kept`, `__n`) | Share of the source's non-grace notes in each voice tier that are kept. **Tier:** at the note's onset t, over every source note sounding at t in any part: *top* = none is higher; *bass* = none is lower, and the note is not alone; *inner* = the rest. A note alone is top. Equal pitch counts as not higher, so unisons tie upward. The tier follows sounding pitch, not part. **Kept:** some output note in any part has the same pitch and an onset within a 16th (\|dt\| < 1/4 quarter, the Note-F1 tolerance). Pooled as sums of `__kept` / `__n`. |
| `retention__by_source_part` | the same kept share per source part (Vn1, Vn2, Va, Vc). Shows a melody that the skyline rule misclassifies. |
| `weighted_fidelity__A`, `__B`, `__C` | Σ_tier w·kept / Σ_tier w·n, with the BLOCK4.md 2b weights (top / bass / inner): A = 1 / 0.8 / 0.25; B = 1 / 1 / 0.7; C = 1 / 1 / 1 (= plain retention). |
| `double_stop_events` | (part, onset t) pairs where ≥ 2 output notes of that part sound at t (a new note against a held one counts) |
| `unneeded_double_stops` (and `__per_100`, `__per_100_source`, `__by_part`) | the double-stop events whose pitch set does **not** sound together within one source part at t. Per 100 output notes, and per 100 source notes (the denominator that dropping cannot shrink). |

**Not a harness field: the intervention rate.** This is the share of committed notes whose top joint
option the mask blocked. It is a property of a masked decoder with a policy, not of an output. It is
logged by the decoder (`model/decode.py` diag `masked_interventions`) and reported next to these fields.

---

## 7. Outputs

`python -m arrangement.eval.harness RECORDS.jsonl [...] --out DIR [--workers N] [--no-soft]`

| File | Content |
|---|---|
| `metrics.jsonl` | one nested metric record per arrangement record: `metrics_version`, `record_id` (content hash of the record), system, seed, input_id, ensemble, `playability`, `fidelity.vs_source`, `fidelity.vs_reference`, `texture`, `near_limit`, `soft` |
| `metrics.csv` | the same, flattened to scalar columns (`section.field[.index]`) for joining across runs |
| `seeds.jsonl` | seed-group rows (§6) |
| `run.json` | spec version, inputs, record counts, SHA-1 of every config file |

Data files only; nothing is printed as a summary.

---

## Changelog

- **1.0.0-draft (2026-10-07).** First draft, written before any model exists. Awaiting approval.
- **1.1.0-draft (2026-10-08).** Playability follows checker-v2: five new check types (multistop, bow, shift
  for strings; duplicate for polyphonic non-string instruments; hand_leap for keyboards), agreed with the
  user after a MuseScore inspection showed v1 passing unplayable cello chords. Each is reported separately,
  with `__applies` defined per instrument. `near_limit` is not yet computed for the five new checks (empty
  histograms). No other metric changed. Every baseline is re-scored under 1.1.0; results under 1.0.0 stay on
  record (git tag `metrics-1.0.0-draft`).
- **1.2.0-draft (2026-10-09).** Playability follows checker-v3, agreed with the user after a MuseScore
  inspection of the checker-v2-masked trio. It showed fast successions of triple stops, overlapping runs read
  as chords, and tight violin clusters, all passing v2. Three new string checks:
  - triple_onset: 3+ sounding notes must all start together;
  - triple_stretch: tighter stretch for 3+ notes, cello 4 and violin/viola 5;
  - triple_rate: consecutive 3+-note moments at least 1 quarter apart.

  The bow threshold changes from 2 quarters to 0.5. `near_limit` is not computed for the new checks.
  No other metric changed. Every baseline is re-scored under 1.2.0, and results under 1.1.0 stay on record
  (git tag `checker-v2`).
- **1.3.0-draft (2026-10-12).** Playability follows checker-v4, agreed with the user after reviewing the
  checker-v3-masked trio (held notes under fast lines, re-struck held pitches). Three new string checks:
  - double_onset: two sounding notes must start together;
  - restrike: no new note on a pitch that is still sounding;
  - double_rate: consecutive 2+-note onsets at least 0.5 quarter apart, except the same double stop
    repeated.

  No other metric changed.
- **1.4.0-draft (2026-10-13).** New section 6b, reduction metrics for Block 4 (BLOCK4.md 2f):
  - retention per voice tier and per source part;
  - weighted fidelity under weight settings A, B and C;
  - unneeded double stops.

  No existing metric changed, and playability is still checker-v4. Every baseline is re-scored under
  1.4.0 before any RL run (`model/rerun_baselines.py`).
- **1.5.0-draft (2026-10-14).** Playability follows checker-v5, agreed with the user after reviewing
  Bridge bars 60–75:
  - triple stops on violin and viola must fit a normal hand position (stretch ≤ 4 semitones; was 5,
    U15); cello is unchanged at 4;
  - new string check `triple_recover`: at least 1 quarter from a 3+-note onset to the next onset in
    the part (U19).

  Nothing else changed. Every baseline is re-scored under 1.5.0, and the 1.4.0 results stay on
  record (tag `checker-v4`).
