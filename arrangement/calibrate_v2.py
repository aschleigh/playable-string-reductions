"""Calibrate the two unsourced checker-v2 thresholds on the TRUE parts of the dev
split (same split as calibrate.py), as the tightest values those scores pass:

  bow_sustain_max_dur (U10): at every onset where >= 3 notes sound in a string part,
      the 3rd-longest of them must be <= d   ->  d = max over dev of that value.
  shift.min_time (U11): a note whose every predecessor needs a hand move > 17 passes
      iff some such predecessor is >= t earlier  ->  t = min over dev of the largest
      such gap.

    python -m arrangement.calibrate_v2 [--workers N]
Writes results/calibration/calibration_v2.json. Values are copied into
config/instruments.yaml by hand.
"""
from __future__ import annotations

import argparse
import json
from bisect import bisect_right
from fractions import Fraction as F
from multiprocessing import Pool

import numpy as np

from arrangement.checker import rules_v2 as R2
from arrangement.corpus import ROOT, load_cached
from arrangement.instruments import load_ensemble
from arrangement.tune_assigner import is_dev, ok_keys

OUT = ROOT / "results" / "calibration"


def per_movement(key: str) -> dict:
    ens = load_ensemble("quartet")
    piece = load_cached(key)
    out = {"bow3": [], "shift_gaps": [], "multistop_fail": 0, "multistop_sets": 0}
    for p, inst in enumerate(ens.instruments):
        sp = inst.strings
        ev = [e for e in piece.events if e.part_id == p]
        ng = sorted((F(e.onset).limit_denominator(10_000), F(e.duration).limit_denominator(10_000), e.pitch)
                    for e in ev if not e.is_grace)
        onsets = sorted({o for o, _, _ in ng})
        active, k = [], 0
        for t in onsets:
            while k < len(ng) and ng[k][0] <= t:
                active.append(ng[k]); k += 1
            active = [n for n in active if n[0] + n[1] > t]
            if len(active) >= 3:
                out["bow3"].append(float(sorted((n[1] for n in active), reverse=True)[2]))
            if 2 <= len(active) <= len(sp.open):
                out["multistop_sets"] += 1
                ok, _ = R2.placement(tuple(sorted(n[2] for n in active)), sp.open, sp.max_offset, sp.max_stretch)
                out["multistop_fail"] += not ok
        allnotes = sorted((F(e.onset).limit_denominator(10_000), F(e.duration).limit_denominator(10_000), e.pitch,
                           e.is_grace) for e in ev)
        by_end = sorted((o + d, i) for i, (o, d, x, g) in enumerate(allnotes))
        ends = [e for e, _ in by_end]
        for c, (oc, dc, xc, gc) in enumerate(allnotes):
            j = bisect_right(ends, oc) - 1
            block, M = [], None
            while j >= 0:
                e, a = by_end[j]
                if M is not None and e < M:
                    break
                j -= 1
                if a == c or (gc and allnotes[a][3] and allnotes[a][0] == oc):
                    continue
                M = e
                block.append(a)
            if not block:
                continue
            moves = [(R2.shift(allnotes[a][2], xc, sp.open, sp.max_offset), oc - allnotes[a][0]) for a in block]
            if all(m > sp.shift_max_semitones for m, _ in moves):
                out["shift_gaps"].append(float(max(g for _, g in moves)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args(argv)
    keys = ok_keys()
    with Pool(a.workers) as pool:
        rows = dict(zip(keys, pool.map(per_movement, keys)))
    res = {}
    for split, sel in (("dev", [k for k in keys if is_dev(k)]), ("heldout", [k for k in keys if not is_dev(k)])):
        b = [x for k in sel for x in rows[k]["bow3"]]
        g = [x for k in sel for x in rows[k]["shift_gaps"]]
        res[split] = {"movements": len(sel), "n_triple_or_more_moments": len(b),
                      "bow3_max": max(b) if b else None,
                      "bow3_quantiles": {q: float(np.quantile(b, q / 100)) for q in (50, 90, 99, 99.9)} if b else None,
                      "n_big_shifts": len(g), "shift_gap_min": min(g) if g else None,
                      "shift_gap_quantiles": {q: float(np.quantile(g, q / 100)) for q in (0.1, 1, 10, 50)} if g else None,
                      "multistop_sets": sum(rows[k]["multistop_sets"] for k in sel),
                      "multistop_fail": sum(rows[k]["multistop_fail"] for k in sel)}
    res["calibrated"] = {"bow_sustain_max_dur": res["dev"]["bow3_max"], "shift_min_time": res["dev"]["shift_gap_min"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration_v2.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
