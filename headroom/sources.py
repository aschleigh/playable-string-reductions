"""Evaluation set for the headroom measurement (DECISION.md amendment A1).

    python -m headroom.sources [--workers N]

Sources = a seeded random sample of the non-dev OpenScore quartet movements
(never used for assigner tuning or transition calibration). Each movement is
exported to data/sources/<idx>.json with
  notes: [part_id, onset, duration, pitch]   non-grace notes only, quarter notes
                                             as exact "p/q" strings
  bars:  [[start, length], ...]              the repeat-expanded measure
                                             timeline, same score object
                                             parse_score builds events from
  parts: declared part names (Vn1, Vn2, Va, Vc)
Grace notes are dropped for every system and control (no duration to encode).
"""
from __future__ import annotations

import argparse
import json
import random
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

from music21 import stream

from arrangement.corpus import ROOT, load_cached, manifest
from arrangement.parse import load_raw_score, slice_movement
from arrangement.tune_assigner import is_dev

HEAD = ROOT / "headroom"
DATA = HEAD / "data" / "sources"
N_EVAL = 150          # pre-registered sample size (DECISION.md A1)
SEED = 0


def eval_keys() -> list[str]:
    rows = sorted((r for r in manifest() if r["status"] == "ok" and not is_dev(r["key"])), key=lambda r: r["key"])
    return sorted(random.Random(SEED).sample([r["key"] for r in rows], N_EVAL))


def _q(x) -> str:
    f = Fraction(x).limit_denominator(10_000)
    return f"{f.numerator}/{f.denominator}"


def bar_timeline(file: str, movement: int, expanded: bool) -> list[tuple[Fraction, Fraction]]:
    s = slice_movement(load_raw_score(ROOT / file), movement)
    if expanded:
        s = s.expandRepeats()
    part = s.parts[0]
    ms = list(part.getElementsByClass(stream.Measure))
    starts = [Fraction(m.getOffsetInHierarchy(part)).limit_denominator(10_000) for m in ms]
    last = Fraction(ms[-1].duration.quarterLength).limit_denominator(10_000)
    # length = gap to the next start (absorbs tuplet rounding in measure durations)
    return [(a, b - a) for a, b in zip(starts, starts[1:])] + [(starts[-1], last)]


def export(args: tuple[int, str]) -> dict:
    idx, key = args
    row = next(r for r in manifest() if r["key"] == key)
    piece = load_cached(key)
    bars = bar_timeline(row["file"], row["movement"], row["repeats_expanded"])
    notes = [[e.part_id, _q(e.onset), _q(e.duration), e.pitch] for e in piece.events if not e.is_grace]
    end = max(Fraction(n[1]) + Fraction(n[2]) for n in notes)
    n_appended = 0
    while bars[-1][0] + bars[-1][1] < end:   # parts can run past the first part's last measure
        bars.append((bars[-1][0] + bars[-1][1], bars[-1][1]))
        n_appended += 1
    bar_end = bars[-1][0] + bars[-1][1]
    contiguous = all(bars[i][0] + bars[i][1] == bars[i + 1][0] for i in range(len(bars) - 1))
    rec = {"idx": idx, "key": key, "parts": [p.name for p in piece.parts], "notes": notes,
           "bars": [[_q(a), _q(b)] for a, b in bars],
           "n_grace_dropped": sum(e.is_grace for e in piece.events), "n_bars_appended": n_appended,
           "checks": {"bars_contiguous": contiguous, "starts_at_zero": bars[0][0] == 0,
                      "notes_end_within_bars": end <= bar_end}}
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / f"{idx:03d}.json").write_text(json.dumps(rec))
    return {"idx": idx, "key": key, "n_notes": len(notes), "n_bars": len(bars), "n_bars_appended": n_appended,
            "n_grace_dropped": rec["n_grace_dropped"], **rec["checks"]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args(argv)
    keys = eval_keys()
    with Pool(a.workers) as pool:
        rows = pool.map(export, list(enumerate(keys)), chunksize=1)
    (HEAD / "data" / "eval_set.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    bad = [r for r in rows if not (r["bars_contiguous"] and r["starts_at_zero"] and r["notes_end_within_bars"])]
    print(len(rows), "movements,", sum(r["n_notes"] for r in rows), "notes,", sum(r["n_bars"] for r in rows),
          "bars; timeline problems:", len(bad))
    for r in bad:
        print("  ", r)


if __name__ == "__main__":
    main()
