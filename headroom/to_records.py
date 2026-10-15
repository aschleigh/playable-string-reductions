"""Convert the headroom sweep (sources + system outputs) into arrangement records
(arrangement/eval/record.py), so the evaluation harness can read them.

    python -m headroom.to_records [--workers N] [--limit K]

Writes headroom/data/records/<system>__<regime>.jsonl. Same pairing as
headroom/measure.py: rule-based systems and the control carry `assignment`;
neural systems carry only output notes (off-ensemble programs dropped). The
quartet floor is the true parts, with the source as `reference`. AMT carries
its 32-bar `window`.
"""
from __future__ import annotations

import argparse
import json
import zlib
from collections import defaultdict
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.assign import continuity, naive
from arrangement.eval.record import ArrangementRecord, Score, make_score, save
from arrangement.instruments import load_ensemble
from headroom.measure import OUT, PRIMARY, PROGRAM_PART, REFERENCE, REGIMES, SRC, _arrays

HEAD = Path(__file__).resolve().parent
DEST = HEAD / "data" / "records"
QUARTET = [("Violin 1", "violin"), ("Violin 2", "violin"), ("Viola", "viola"), ("Violoncello", "cello")]


def _parts(regime):
    e = load_ensemble(regime)
    return [(n, i.key) for n, i in zip(e.part_names, e.instruments)]


def records_for(path: Path) -> dict[str, list[ArrangementRecord]]:
    d = json.loads(path.read_text())
    notes = sorted(((int(p), Fraction(o), Fraction(du), int(x)) for p, o, du, x in d["notes"]),
                   key=lambda n: (n[1], n[3], n[0], n[2]))
    src = make_score(QUARTET, notes)
    bars = tuple((Fraction(a), Fraction(b)) for a, b in d["bars"])
    plain = [(n[1], n[2], n[3]) for n in src.notes]
    arr = _arrays(plain)
    base = dict(input_id=d["key"], source=src, bars=bars, meta={"idx": d["idx"]})
    out: dict[str, list[ArrangementRecord]] = defaultdict(list)

    def assigned(system, regime, a, seed=None, **kw):
        parts = _parts(regime)
        o = make_score(parts, [(int(p), n[1], n[2], n[3]) for p, n in zip(a, src.notes) if p >= 0])
        out[f"{system}__{regime}"].append(ArrangementRecord(
            system=system, seed=seed, ensemble=regime, output=o, assignment=tuple(int(x) for x in a),
            reference_source_parts=tuple(tuple(r) for r in REFERENCE[regime]), **base, **kw))

    for regime in REGIMES:
        ens = load_ensemble(regime)
        P = len(ens)
        if regime == "quartet":
            assigned("floor", regime, [n[0] for n in src.notes], reference=src)
        assigned("naive", regime, naive(arr, ens))
        if P > 1:
            assigned("continuity", regime, continuity(arr, ens))
        rng = np.random.default_rng(zlib.crc32(f"{d['key']}|control|{regime}".encode()))
        assigned("control", regime, rng.integers(0, P, len(plain)), seed=0)
    for system, regime in [(PRIMARY[r], r) for r in PRIMARY] + [("amt", "trio")]:
        f = OUT / system / regime / path.name
        if not f.exists():
            continue
        g = json.loads(f.read_text())
        m = PROGRAM_PART[regime]
        kept = [(m[int(pr)], Fraction(o), Fraction(du), int(x)) for pr, o, du, x in g["notes"] if int(pr) in m]
        seed = zlib.crc32(f"{d['key']}|{system}|{regime}".encode())
        kw = {"window": (Fraction(0), Fraction(g["end_q"]))} if system == "amt" else {}
        out[f"{system}__{regime}"].append(ArrangementRecord(
            system=system, seed=seed, ensemble=regime, output=make_score(_parts(regime), kept),
            reference_source_parts=tuple(tuple(r) for r in REFERENCE[regime]),
            meta={**base["meta"], "n_off_ensemble": len(g["notes"]) - len(kept)},
            **{k: v for k, v in base.items() if k != "meta"}, **kw))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    paths = sorted(SRC.glob("*.json"))[: a.limit]
    with Pool(a.workers) as pool:
        parts = pool.map(records_for, paths, chunksize=1)
    allr: dict[str, list] = defaultdict(list)
    for p in parts:
        for k, v in p.items():
            allr[k] += v
    DEST.mkdir(parents=True, exist_ok=True)
    for k, v in sorted(allr.items()):
        save(v, DEST / f"{k}.jsonl")
        print(k, len(v))


if __name__ == "__main__":
    main()
