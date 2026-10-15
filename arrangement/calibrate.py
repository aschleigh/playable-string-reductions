"""Corpus calibration of the thresholds that have no orchestration source
(UNSOURCED.md U1-U5): fit them to the TRUE part assignments of the dev split
(the same crc32 split the assigner was tuned on), so the professionally
engraved scores pass by construction there; the other 90% then test whether
the fitted values generalize.

    python -m arrangement.calibrate [--workers N]

Writes results/calibration/calibration.json. Values are copied into
config/instruments.yaml by hand, each marked "CORPUS-CALIBRATED (Un)".

Range high: dev-split maxima proved far too tight on held-out scores (the
top register is heavy-tailed), so the bound is the FULL-CORPUS envelope:
the highest pitch per instrument whose measure carries no harmonic markup
(diamond noteheads, <harmonic>, "flag."/"harm." text; those passages also
print touch points and resulting pitches as notes). The floor's range-high
result is therefore not an independent test.
Transition (time_basis "onset"): leap <= a + b * t, t = onset(next) -
onset(chosen predecessor) in quarter notes. For each b on a grid, the
smallest a that passes every dev transition is a_b = max(leap - b * t); the
chosen b is the one that minimizes the mean allowed leap over the observed
dev transitions (the tightest envelope among those the dev floor passes).
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

from arrangement.checker import check
from arrangement.corpus import ROOT, load_cached
from arrangement.instruments import Transition, load_ensemble
from arrangement.strip import strip_labels
from arrangement.tune_assigner import is_dev, ok_keys

OUT = ROOT / "results" / "calibration"
B_GRID = [0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0]
_PROBE_A = -1000.0   # with b = 1 every transition is reported and t = limit - _PROBE_A


def transitions_and_maxima(key: str) -> dict:
    """All (instrument, leap, t) transitions and per-instrument max pitch for
    the true assignment of one movement."""
    ens = load_ensemble("quartet")
    probe = Transition(_PROBE_A, 1.0, "onset")
    ens = replace(ens, instruments=tuple(replace(i, transition=probe) for i in ens.instruments))
    up, target = strip_labels(load_cached(key))
    notes = up.arrays()
    out = {"leaps": defaultdict(list), "max_pitch": {}}
    for v in check(notes, ens, target.part_id):
        if v.check == "transition":
            out["leaps"][ens.instruments[v.part_id].key].append((v.measured, v.limit - _PROBE_A))
    for p, inst in enumerate(ens.instruments):
        m = target.part_id == p
        if m.any():
            out["max_pitch"][inst.key] = max(out["max_pitch"].get(inst.key, 0), int(notes.pitch[m].max()))
    out["leaps"] = dict(out["leaps"])
    return out


def _top_notes(key: str, k: int = 8) -> list[dict]:
    """Highest k notes per instrument in one movement, as triage records."""
    piece = load_cached(key)
    ens = load_ensemble("quartet")
    out = []
    for p, inst in enumerate(ens.instruments):
        evs = sorted((e for e in piece.events if e.part_id == p), key=lambda e: -e.pitch)[:k]
        for e in evs:
            out.append({"key": key, "instrument": inst.key, "part": piece.parts[p].name, "check": "range",
                        "measured": e.pitch, "limit": 0,
                        "notes": [{"pitch": e.pitch, "onset": e.onset, "duration": e.duration, "measure": e.measure}]})
    return out


def range_high_envelope(keys: list[str], workers: int) -> dict:
    from arrangement.triage import HARMONIC, annotate
    with Pool(workers) as pool:
        cands = [c for rows in pool.map(_top_notes, keys) for c in rows]
    out = {}
    for inst in sorted({c["instrument"] for c in cands}):
        mine = sorted((c for c in cands if c["instrument"] == inst), key=lambda c: -c["measured"])
        skipped = []
        for c in mine:
            if set(annotate(c)["xml_features"]) & HARMONIC:
                skipped.append((c["key"], int(c["measured"])))
                continue
            out[inst] = {"high": int(c["measured"]), "at": c["key"], "measure": c["notes"][0]["measure"],
                         "skipped_harmonic_passages": len(skipped), "highest_skipped": skipped[:3]}
            break
    return out


def fit_envelope(leap: np.ndarray, t: np.ndarray) -> dict:
    best = None
    for b in B_GRID:
        a = float(np.max(leap - b * t))
        mean_allowed = float(np.mean(a + b * t))
        if best is None or mean_allowed < best["mean_allowed"]:
            best = {"a": a, "b": b, "mean_allowed": mean_allowed}
    return best


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=48)
    args = ap.parse_args(argv)
    keys = [k for k in ok_keys() if is_dev(k)]
    with Pool(args.workers) as pool:
        rows = pool.map(transitions_and_maxima, keys)
    leaps: dict[str, list] = defaultdict(list)
    maxp: dict[str, int] = {}
    for r in rows:
        for k, v in r["leaps"].items():
            leaps[k] += v
        for k, v in r["max_pitch"].items():
            maxp[k] = max(maxp.get(k, 0), v)
    result = {"dev_movements": len(keys), "dev_range_high": maxp,
              "range_high_envelope": range_high_envelope(ok_keys(), args.workers), "transition": {}}
    for k, v in sorted(leaps.items()):
        a = np.array(v)
        env = fit_envelope(a[:, 0], a[:, 1])
        q = {f"leap_p{p}": float(np.percentile(a[:, 0], p)) for p in (50, 99, 99.9, 100)}
        result["transition"][k] = {"n": len(v), **env, **q}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
