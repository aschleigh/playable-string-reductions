# Step 4: checker validation on real scores

687 OpenScore string-quartet movements, 2,396,332 notes, config of
`arrangement/config/instruments.yaml` (thresholds: open-string lows and 4-string chords sourced;
upper ranges and transitions CORPUS-CALIBRATED, see UNSOURCED.md). Violations per 100 assigned
notes, one row per check type. No aggregate score.

## Rates per 100 notes

| Check | Floor (true parts) | Ceiling (naive) | Continuity | Floor, first run | Naive, first run |
|---|---|---|---|---|---|
| simultaneity | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| range | 0.0007 | 0.0005 | 0.4435 | 0.0048 | 0.0014 |
| chord_size | 0.0000 | 0.5623 | 0.0000 | 0.0003 | 0.3318 |
| hand_span | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| transition | 0.0057 | 0.0000 | 0.0222 | 0.0389 | 0.0155 |

Simultaneity and hand span are 0 by construction for strings (not monophonic; no keyboard).
"First run" = before the parser fixes and the threshold decisions (PLAN.md decisions 3, 10-12).

## Distribution across movements

Per-movement rate per 100 notes. Top-5% share = fraction of that check's violations in the worst 5% of movements.

| Assignment | Check | Violations | Movements with any | Median | p90 | p99 | Max | Top-5% share | Worst movements (count) |
|---|---|---|---|---|---|---|---|---|---|
| floor | range | 17 | 5 | 0.000 | 0.000 | 0.000 | 0.097 | 100% | Zemlinsky String_Quartet_No.2,_Op.15 m01 (10); Schulhoff String_Quartet_No.1 m04 (2); Koechlin String_Quartet_No.1,_Op.51 m02 (2) |
| floor | chord_size | 0 | 0 | | | | | | |
| floor | transition | 136 | 67 | 0.000 | 0.000 | 0.078 | 0.148 | 76% | Kalliwoda String_Quartet_No.3,_Op.90 m01 (8); Kalliwoda String_Quartet_No.3,_Op.90 m04 (7); Zemlinsky String_Quartet_No.2,_Op.15 m01 (6) |
| naive | range | 12 | 2 | 0.000 | 0.000 | 0.000 | 0.097 | 100% | Zemlinsky String_Quartet_No.2,_Op.15 m01 (10); Schulhoff String_Quartet_No.1 m04 (2) |
| naive | chord_size | 13474 | 491 | 0.216 | 1.330 | 2.969 | 12.579 | 34% | Kalliwoda String_Quartet_No.3,_Op.90 m04 (326); Grieg String_Quartet_No.1,_Op.27 m04 (292); Schulhoff String_Quartet_No.1 m04 (259) |
| naive | transition | 0 | 0 | | | | | | |
| continuity | range | 10627 | 559 | 0.238 | 1.095 | 3.523 | 6.862 | 29% | Zemlinsky String_Quartet_No.2,_Op.15 m01 (185); Schulhoff String_Quartet_No.1 m01 (184); Wolf String_Quartet m01 (181) |
| continuity | chord_size | 0 | 0 | | | | | | |
| continuity | transition | 532 | 187 | 0.000 | 0.064 | 0.211 | 0.659 | 54% | Schubert String_Quartet_in_D_minor, m02 (47); Grieg String_Quartet_No.1,_Op.27 m04 (38); Beethoven String_Quartet_No.16_in_F_ m04 (14) |

Full per-movement counts: `per_movement.csv`. Floor triage: `TRIAGE.md`.

## Reading it

1. **Floor:** 153 violations, none a parser bug (TRIAGE.md). Transition violations are real
   leaps just beyond the envelope fitted on the 10% dev split, all in held-out movements. That is
   the one independent test of the calibration, and it shows the dev split underestimates the tail.
   Range-high is calibrated on the full corpus, so passing it is not evidence.
2. **Ceiling:** naive fails chord size (0.56 per 100 notes, in 491 movements) and almost nothing else.
   An envelope wide enough to pass real quartet writing never trips on naive's pitch-banded lines
   (naive transitions: 0). For string quartet, the hard tier
   rejects over-full chords and little else: it is a floor, not a discriminator.
3. **Continuity** has no chord-size violations, but range 0.44 per 100 notes: spreading pushes low notes into upper parts when the cello is busy, and the checker catches it.

## Checker speed on real movements (single process, best of 5; `tests/bench_corpus.py`)

| Sample | Median notes | Floor ms (median / max) | Naive ms (median / max) | Movements > 10 ms |
|---|---|---|---|---|
| 25 largest movements | 8645 | 4.48 / 9.24 | 4.81 / 11.3 | 1 |
| 75 random movements | 2776 | 1.27 / 3.2 | 1.32 / 3.51 | 0 |

`checker_ms_floor` in summary.json is measured under 48 parallel workers and overstates this.
