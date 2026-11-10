"""Block 7 Step 0 (R76/R77): the fresh confirmation set, from DCML note tables (MuseScore 3 sources, extracted by ms3).

    python -m arrangement.fresh_corpus      -> model/data/fresh_sources.jsonl (ArrangementRecord, system "fresh_source")

Movements whose work is not in OpenScore (checked by composer, opus and number, R77):
  - ABC (Beethoven, DCML; decision 7 kept it out of training): Op. 59/1, 59/2, 74, 95, 132 (21 movements);
  - DCML mendelssohn_quartets: Op. 44 No. 3 (4 movements);
  - DCML pleyel_quartets: all (6 movements; no Pleyel in OpenScore).
Licences: ABC CC BY-NC-SA 4.0; mendelssohn_quartets and pleyel_quartets CC BY-NC-SA 4.0. Evaluation only; not
redistributed (raw_corpora and model/data are excluded from the GitHub export).
Conversion: staff 1-4 -> Vn1, Vn2, Va, Vc; onsets `quarterbeats` (exact fractions, repeats NOT expanded); durations
4 x `duration` (whole-note fractions); tied chains (1 ... 0 ... -1) merged into one note; grace notes dropped; bars from
the measures table (`quarterbeats`, `act_dur`). Notes and bars of alternative endings beyond the first (no
`quarterbeats`) are left out. These movements are not decoded or listened to before Step 5.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

from arrangement.eval.record import ArrangementRecord, make_score, save

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_corpora"
OUT = ROOT / "model" / "data" / "fresh_sources.jsonl"
SETS = [  # (corpus dir, file prefix filter, label)
    (RAW / "ABC", ("n07op59-1", "n08op59-2", "n10op74", "n11op95", "n15op132"), "Beethoven (ABC)"),
    (RAW / "fresh" / "mendelssohn_quartets", ("05op44,3",), "Mendelssohn (DCML)"),
    (RAW / "fresh" / "pleyel_quartets", ("",), "Pleyel (DCML)"),
]
QUARTET = [("Violin 1", "violin"), ("Violin 2", "violin"), ("Viola", "viola"), ("Violoncello", "cello")]


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def movement(corpus: Path, stem: str):
    notes = []
    open_ties = {}
    for r in _rows(corpus / "notes" / f"{stem}.notes.tsv"):
        if r.get("gracenote") or not r.get("quarterbeats"):     # grace notes; alternative endings (no place on the timeline)
            continue
        staff, pitch = int(r["staff"]), int(r["midi"])
        if not 1 <= staff <= 4:
            continue
        on, du = F(r["quarterbeats"]), 4 * F(r["duration"])
        tie = (r.get("tied") or "").strip()
        key = (staff, pitch)
        if tie in ("0", "-1") and key in open_ties:          # continue / end a tied chain
            k = open_ties[key]
            p, o, d, x = notes[k]
            notes[k] = (p, o, on + du - o, x)
            if tie == "-1":
                del open_ties[key]
            continue
        notes.append((staff - 1, on, du, pitch))
        if tie == "1":
            open_ties[key] = len(notes) - 1
    bars = [(F(r["quarterbeats"]), 4 * F(r["act_dur"])) for r in _rows(corpus / "measures" / f"{stem}.measures.tsv")
            if r.get("quarterbeats")]
    return notes, tuple(bars)


def main():
    recs = []
    for corpus, prefixes, label in SETS:
        for f in sorted((corpus / "notes").glob("*.notes.tsv")):
            stem = f.name[: -len(".notes.tsv")]
            if not any(stem.startswith(p) for p in prefixes):
                continue
            notes, bars = movement(corpus, stem)
            src = make_score(QUARTET, notes)
            recs.append(ArrangementRecord(system="fresh_source", seed=None, input_id=f"fresh__{corpus.name}__{stem}",
                                          ensemble="quartet", source=src, output=src, bars=bars,
                                          meta={"corpus": label, "repeats_expanded": False}))
            print(f"{label:20s} {stem:24s} {len(notes):6d} notes {len(bars):4d} bars", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    save(recs, OUT)
    print(f"{len(recs)} movements -> {OUT}")


if __name__ == "__main__":
    main()
