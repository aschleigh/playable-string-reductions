# Unsourced thresholds

No value below has an orchestration source. Since 2026-10-06 they are
CORPUS-CALIBRATED (PLAN.md decision 12, `arrangement/calibrate.py`,
`results/calibration/calibration.json`): envelopes of the professionally
engraved OpenScore quartets, to be reported as data-derived, not sourced.
Replace each with a reference value when one is found.

| Code | Field | Current value (was placeholder) | Notes |
|---|---|---|---|
| U0 | transition functional form | `leap <= a + b * t` | Linear form is an assumption, not a sourced model. Since 2026-10-06 (PLAN.md decision 3) t = next onset - previous note's onset (`time_basis: onset`); the release-based rule is still implemented. String crossing, open strings and position shifts are not distinguished. |
| U1 | violin `range.high` | 103 G7 (was 100) | Full-corpus max outside harmonic passages (Janáček No.2 iv). Dev-split max would fail held-out notes, so this is not independently validated. |
| U2 | viola `range.high` | 92 G♯6 (was 91) | as U1 (Zemlinsky No.2). Koechlin's 96 is in a harmonic passage. |
| U3 | cello `range.high` | 86 D6 (was 81) | as U1 (Zemlinsky No.2). Borodin's 88 is a "Flag." harmonic. |
| U4 | strings `transition.max_leap_at_zero_gap` | violin 36, viola 30, cello 29 (was 24) | `a` in U0, dev-split envelope; 118 held-out floor leaps exceed it (up to 43 on violin). |
| U5 | strings `transition.semitones_per_quarter_gap` | violin 0, viola 0, cello 1 (was 12) | `b` in U0. The tightest passing envelope is nearly flat: the largest real leaps happen at short time spans (string crossings, open strings). Tempo-blind. |
| U6 | flute `range.low` | 60 C4 | Added in checker-v1.1. Common C-foot compass; B3 (59) with a B foot. Not verified against a reference. |
| U7 | flute `range.high` | 96 C7 | Added in checker-v1.1. Common upper limit; professionals reach higher. Not verified against a reference. |
| U8 | piano `hand_span.semitones` | 14 (major ninth) | Added in checker-v1.1. Per-hand reach; varies widely between players. Not verified against a reference. |
| U9 | violin, viola `strings.max_stretch` | 9 semitones | checker-v2. A fingered tenth (1st to stretched 4th finger), the advanced-player extreme; Claude's judgement, agreed with the user 2026-10-08. Cello's 7 (thumb to 4th) is the user's own limit, cited [User]. One semitone limit is an approximation: semitones get closer together higher up the string. |
| U10 | strings `strings.bow_sustain_max_dur` | 0.5 quarters (checker-v3; was 2 in checker-v2) | checker-v3: set by the user (2026-10-09) on performance grounds: triple stops are rolled or broken, so only two strings can be held. Superseded checker-v2 value: 2 quarters, the Dev-split envelope of the true parts (calibrate_v2.py). Held-out real scores go up to 6 quarters: notated sustained triple stops, which players roll and then hold two notes. 86 floor violations; see results/validation_v2. |
| U11 | strings `strings.shift.min_time` | 0.25 quarters | checker-v2. No dev movement has a forced hand move > 17 semitones, so this is the full-corpus envelope (13 such shifts, the fastest with a 16th of time). Not independently validated. |
| U12 | piano `hand_leap.max_leap_at_zero_gap` | 24 semitones | checker-v2. Placeholder; no piano corpus to calibrate on. |
| U13 | piano `hand_leap.semitones_per_quarter_gap` | 12 | checker-v2. Placeholder, as U12. |
| U14 | cello `strings.triple.max_stretch` | 4 semitones | checker-v3. Proposed by Claude, approved by the user (2026-10-09). **Confirmed by the user (2026-10-15): "allow extended position"** for cello triple stops; 4 semitones is extended position on the cello, so the value is unchanged. Not corpus-calibrated; see results/validation_v3 for what the floor makes of it. |
| U15 | violin, viola `strings.triple.max_stretch` | 4 semitones (checker-v5; was 5) | checker-v3, tightened in checker-v5 by the user (2026-10-14): triple stops in normal position only. Bridge bar 75 (open G, E♭4 low-1, E♭5 extended-4; stretch 5) is unplayable. Cello unchanged (U14, 4 = extended position for cello). |
| U16 | strings `strings.triple.min_gap` | 1 quarter | checker-v3. As U14. Tempo-blind: the corpus has no reliable tempo. |
| U17 | strings triple_onset (no number) | 3+ sounding notes must start together | checker-v3. A rule, not a threshold. Listed because it is unsourced: it rules out a held note under a new double stop. |
| U18 | strings `strings.double.min_gap` | 0.5 quarter | checker-v4. Proposed by Claude, approved by the user (2026-10-12). Not corpus-calibrated. Tempo-blind. It also switches on two rules with no number: double_onset (two sounding notes must start together) and restrike (no new note on a pitch that is still sounding). Exempt: the same double stop repeated (no new fingering); in the draft floor run that was 2/3 of double_rate floor violations. |
| U19 | strings `strings.triple.recover` | 1 quarter | checker-v5 (`triple_recover`). From the user's review (2026-10-14): a triple stop needs time before the next note in the part (bar 75: an eighth-note chord straight into 16ths is unplayable). Proposed by Claude from that verdict, approved by the user. Not corpus-calibrated; tempo-blind. |
| U20 | S2 target rule `CELLO_MOVED_MAX` (model/targets_s2.py) | D5 (MIDI 74; was G4, 67, in S2) | Training-target rule, not a checker threshold. **Set by the user (2026-10-15): "you can go up to high D (in thumb position) for cello"**, read as D5 (MIDI 74), an eleventh above the open A string (A3), in thumb position. Notes moved into the cello above D5 go down an octave. The cello's own source notes are not restricted. Used from the S2b targets on (BLOCK5.md Step 1a). |
| U21 | S2 target rule `VIOLA_INNER_DS_GAP` (model/targets_s2.py) | 2 quarters | Training-target rule, not a checker threshold. User (2026-10-15): viola double stops "slightly stricter"; Claude's rule, approved by the user ("the open rule looks good"): a source double stop made only of inner-voice notes is accepted in the viola only if no other viola double stop began within 2 quarters before it. Calibrated on 200 train movements: viola target rate 6.11 -> 4.45 per 100 notes (gap 0.5: 5.88; 1: 5.28; 4: 3.68), aimed at ~4.5, slightly under the real viola 5.1. Melody and bass retention unchanged; inner retention 0.581 -> 0.569. Tempo-blind. |

Sourced values: lowest pitch = lowest open string, and `max_chord = 4` = four strings
(Adler, *The Study of Orchestration*, 4th ed., 2016). Scordatura (for example a cello C
string tuned down) would legitimately break the low bound. The floor triage should report
such cases rather than lowering the bound.

Test-fixture thresholds in `tests/golden/instruments_test.yaml` are not claims about any
instrument.

## Soft tier (provisional, Step 4)

Thresholds in `arrangement/config/soft.yaml`. They are **costs, not violations**, and all of them
are placeholders awaiting calibration by the performer study. None has an orchestration source.
Only the open-string tunings used by the crossing cost are sourced (Adler 2016).

| Code | Field | Current value | Notes |
|---|---|---|---|
| S1 | `assumed_qpm` | 100 | One fixed tempo converts `_seconds` thresholds to quarter notes. The corpus has no reliable tempo (NOTES.md, tempo-aware transitions). |
| S2a | flute `breath.min_breath_gap` | 0.5 q | Shortest gap counted as a breath point. |
| S2b | flute `breath.max_phrase_seconds` | 10 s | Longest phrase without cost. Depends on register and dynamics, which are ignored. |
| S3 | strings `bow.max_bow_seconds` | 8 s | Longest single-bow note without cost. Depends on dynamics and bow speed, which are ignored. |
| S4 | strings `shift.frame_semitones` | 7 | Interval reachable without a shift. A crude stand-in: open strings and string crossings also reach wide intervals without shifting. |
| S5 | strings `shift.max_shift_ioi` | 0.5 q | Shifts after a longer interval are treated as free. |
| S6 | strings `crossing.fast_ioi` | 0.25 q | A crossing faster than this costs 1. The string estimate (highest open string at or below the pitch) ignores alternative fingerings. |
| S7 | `register.comfortable_high` | violin 93 (A6), viola 81 (A5), cello 76 (E5), flute 93 (A6) | Comfortable top, distinct from the hard range high (UNSOURCED U1-U3, U7). |
| S8 | `key` (transposing instruments) | proxy: written notes on black keys | No current instrument transposes, so this is exercised only by a test fixture. The proxy ignores key context (an F# in G major is not awkward). |
| S9 | `repeated.min_ioi` | 0.25 q (all instruments) | Fastest comfortable repetition of one pitch (single tonguing, détaché, piano repetition), at S1's tempo. |
