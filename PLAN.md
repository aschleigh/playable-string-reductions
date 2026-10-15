# PLAN — playability verification layer (string quartet)

Scope: corpus prep, hard-tier checker, rule-based assigner, checker validation.
No model, reward, soft tier, difficulty, or segmentation. Those ideas go in NOTES.md.

## Data (Step 0 findings)

| Source | Format | Count | Declared parts / instruments | License |
|---|---|---|---|---|
| `raw_corpora/StringQuartets` (OpenScore SQ) | `.mxl` (+ paired `.mscx/.mscz`) | 196 files, 179 works, about 1,300 movement candidates by measure-number reset (an upper bound) | Yes. `<score-part>`, `<part-name>`, `<midi-instrument>`; 194 of 196 files are exactly Vn1/Vn2/Va/Vc, 2 have an extra "Klang" part; no `<transpose>` anywhere | CC0 |
| `raw_corpora/ABC` (DCML Beethoven) | `.mscx` → MusicXML via MuseScore CLI (`render.convert_mscx_to_musicxml`) | 70 movements | Yes | CC BY-NC-SA 4.0 |
| Our MIDI | none | 0 | — | — |
| Our Humdrum | none | 0 | — | — |

Other users' directories on this machine hold about 85k MIDI files (piano, jazz, pop909, maestro) and 370 Bach-chorale `.krn` files (`/scratch/joeltjy1`). None of it is chamber strings and none of it is ours, so it is not used.

**MusicXML is the format with declared parts and instrument metadata.** No download is needed: the OpenScore set alone exceeds "several hundred movements". The ABC set mostly duplicates the OpenScore Beethoven quartets, so it is either a cross-check or left out (Q7).

## Module layout (`arrangement/`, existing parse.py/ties.py kept and wrapped)

> **Outdated (noted 2026-10-06):** this is the planned layout. As built: `parse.py` (NoteEvent/ParsedPiece, float quarter-note times, no `qpm`), `backends/`, `corpus.py`, `strip.py`, `checker/{types,batch,incremental,report}.py`, `assign.py`, `validate.py`, `triage.py`, `calibrate.py`.

```
arrangement/
  events.py        NoteEvent, Piece, PartInfo (schema below); immutable, numpy view
  backends/
    base.py        Backend protocol: can_read(path) -> bool; read(path, movement) -> Piece
    musicxml.py    wraps existing parse.py (ties.py merge, sounding pitch, perc exclusion)
    midi.py        degraded path: tracks/channels -> parts, part_inferred=True unless
                   a program/track name maps to a declared instrument (still flagged)
  load.py          load(path, movement=None) -> Piece; dispatch by suffix; cache to .npz
  spec.py          extract_spec(piece) -> EnsembleSpec (n parts, observed range,
                   max simultaneity, instrument id per part)
  strip.py         strip_labels(piece) -> (UnlabeledPiece, target: np.ndarray[int])
  instruments/
    quartet.yaml   per-instrument thresholds, each with a source comment
  checker/
    types.py       Violation, Report
    checks.py      five checks as pure functions over per-part sorted arrays
    state.py       IncrementalChecker (commit / uncommit / would_violate)
    report.py      per-100-note rates per check type, per-piece distribution
  assign.py        naive(piece, ensemble) / continuity(piece, ensemble)
  validate.py      floor + ceiling runs -> results/validation/*.json + summary table
tests/
  golden/          hand-built passages: one per check that fails exactly that check,
                   plus clean passages (written first, no corpus needed)
  test_checker_*.py, test_incremental_equivalence.py, test_determinism.py
  bench_checker.py (pytest-benchmark or timeit; target < 10 ms / movement)
```

## Note-event schema

```python
@dataclass(frozen=True)
class NoteEvent:
    id: int              # dense 0..n-1, stable sort order (onset, pitch, part, voice)
    onset: Fraction      # quarter notes from movement start (float mirror in arrays)
    duration: Fraction   # quarter notes, tie chain merged; 0 for grace
    pitch: int           # sounding MIDI
    part_id: int         # declared part index (the label; removed by strip.py)
    part_inferred: bool  # True on MIDI path without declared instruments
    voice_id: str; staff_id: int; measure: int
    is_grace: bool; tie_group_id: int; is_tied: bool
    qpm: float | None    # local tempo if marked, for the transition check (Q3)
```
`Piece` holds `events`, `parts: list[PartInfo(part_id, name, instrument_key, n_staves, transposition)]`, provenance, warnings, and a struct-of-arrays view (`onset, end, pitch, part`) for the checker.

## Checker interface

```python
@dataclass(frozen=True, order=True)
class Violation:
    check: Literal["simultaneity","range","chord_size","hand_span","transition"]
    part_id: int
    note_ids: tuple[int, ...]   # sorted; always non-empty
    measured: float             # e.g. leap semitones, chord size, span
    limit: float                # threshold from config
    # sort key = (check, part_id, note_ids) -> deterministic output

class Checker:
    def __init__(self, piece_arrays, ensemble: Ensemble, config: Config): ...
    def check(self, assignment: np.ndarray) -> list[Violation]
        # assignment[i] = part index, or -1 = unassigned. Unassigned notes
        # are invisible, so a partial arrangement is checked the same way.

class IncrementalChecker(Checker):
    def commit(self, note_id, part) -> list[Violation]     # new violations only
    def uncommit(self, note_id) -> None                    # for search / backtracking
    def would_violate(self, note_id, part) -> list[Violation]  # no state change
    def mask(self, note_id) -> np.ndarray[bool]            # per part, for decoding
    def violations(self) -> list[Violation]                # current full set
```
Invariant tested: for any assignment, committing notes one at a time in **any** order gives the same `violations()` set as `check(assignment)`, and as each prefix's `check`.
Implementation: each part keeps a sorted interval index (bisect on onset, plus a max-duration bound), so a commit touches only overlapping and adjacent notes, O(log n + k).

Report: `{check: violations_per_100_assigned_notes}` per piece and pooled, plus per-piece histograms and a top-k worst-pieces list. No aggregate score.

## Assigner (does not import checker)
- **naive**: each note goes to a part whose configured range contains the pitch. Overlapping ranges are split into fixed bands at overlap midpoints. No time context.
- **continuity**: processes onset slices in order. Each note's cost is out-of-range penalty + λ·|pitch − part's last pitch| + μ·(switch away from the part that held the previous note in the same voice/line). The slice is solved by min-cost matching, and λ, μ are in config. Matching is per slice, so it does not see later slices (Q6).

## Validation
Floor: all OpenScore movements with real labels. Each violation is dumped with file/measure/notes and triaged as parser-bug or threshold-too-strict in `results/validation/triage.md`. Ceiling: the naive assigner on the same movements. Output is rates per 100 notes per check and the distribution across pieces.

## Open questions (research consequences, so I'm asking before choosing)
1. **Strings are not monophonic.** Should simultaneity (overlap on a monophonic instrument) be off for Vn/Va/Vc, with double/triple stops left to chord-size? Or should strings count as monophonic except for notated chords? Double stops also need adjacent strings, which works like a string "hand span". That isn't one of the five checks: add it, or record it in NOTES.md?
2. **Overlap definition.** Strict `a.end > b.onset`, or with a tolerance for legato overlap from engraving? And do grace notes (duration 0) take part in simultaneity and transition?
3. **Transition.** Is the available time in quarter notes, or in seconds using tempo marks (many scores have only text tempi)? Is the leap measured from the previous note's onset or its release? A "too far in too little time" threshold for cello has no sourced number I know of, so it becomes a placeholder in UNSOURCED.md unless you have a source.
4. **Ties across voices.** ties.py currently merges a tie that crosses voices within the same staff and logs it. Keep that, or refuse to merge?
5. **Repeats.** Expand them (current default) or use the notated surface? Expanding inflates note counts but not rates.
6. **Continuity assigner.** Is per-slice matching (at most one note per part per slice) fair, or does that already count as feasibility awareness you'd rather leave out of the baseline?
7. **Corpus for the floor.** Use OpenScore only (CC0), or also the 70 ABC movements (NC license, overlaps Beethoven)? Should the extra "Klang" parts (2 files) be dropped?
8. **Hand span (keyboard).** The quartet has no keyboard. I'd implement it generically with placeholder thresholds and only test it on golden cases. OK?
9. **Humdrum backend.** No kern data is ours. Stub the interface only, or implement against a fetched KernScores sample later?

## Decisions (approved 2026-10-06: plan + all defaults)
1. Strings: simultaneity check off (`monophonic: false`); double stops are covered by chord size. Adjacent-string constraint → NOTES.md.
2. Overlap is strict (`a.end > b.onset and b.end > a.onset`), no tolerance. Grace notes are excluded from simultaneity / chord size / hand span, included in transition.
3. Transition: time in quarter notes, tempo ignored. **Changed 2026-10-06 (user delegated: "choose the most reasonable option"):** time basis = previous note's *onset* → next onset (`time_basis: onset`). The release-based rule made every legato leap a bare size cap. Both bases stay implemented.
4. Cross-voice ties: merged + logged (unchanged).
5. Repeats: expanded.
6. Continuity assigner: per-onset-slice min-cost matching. **Amended 2026-10-06 (delegated, confirmed):** the configured mode forbids part crossing within a slice. Unconstrained matching made the continuity weight useless (best w_cont = 0); see results/assigner/README.md. The unconstrained mode is still available (`crossing: allow`).
7. Floor corpus: OpenScore only; "Klang" parts dropped (by name, `exclude_part_names` in ensembles/quartet.yaml); ABC unused. Result: 687 movements, 2,397,574 notes, all Vn/Vn/Va/Vc.
8. Hand span: generic, placeholder thresholds, golden-tested only.
9. Humdrum: interface only.
10. Harmonics (delegated 2026-10-06): a diamond touch-point note that shares a chord with a normal note (artificial harmonic) is dropped, and the stopped note is kept as the fingered pitch. Lone diamonds, natural harmonics notated at sounding pitch, and resulting-pitch voices stay as written (a known limitation; 25 floor violations).
11. Shared unisons (delegated 2026-10-06): same part, same pitch, same onset, *different* voices → one note (the longest). Same-voice unisons are kept as deliberate unison double stops.
12. Unsourced thresholds (delegated 2026-10-06): no invented numbers. Range highs = full-corpus envelope outside harmonic passages; transition caps = dev-split envelope of the true parts, tested on the held-out 90%. All labelled CORPUS-CALIBRATED; `arrangement/calibrate.py`.
13. No sixth (double-stop/string-feasibility) check: a tuning-only version separates floor (0.003 per 100 notes) from naive (0.04) far less than chord size does; recorded in NOTES.md.
