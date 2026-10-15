"""Reduction metrics (METRICS.md section 6b, added in 1.4.0-draft; BLOCK4.md 2b and 2f).

Computed on the output against the source; no provenance, no checker, so every system gets them.

Voice tiers (per source note, non-grace): at the note's onset t, over every source note sounding
at t (onset <= t < end) in any part: top = none is higher; bass = none is lower and the note is
not alone; inner = the rest. A note alone is top. Equal pitch counts as "not higher" (unisons tie
upward). Tiers follow sounding pitch, not part (voice crossings move the tier).

Retention: a source note is kept if some output note (any part, non-grace) has the same pitch
and an onset within a 16th (|dt| < 1/4 quarter, the Note-F1 tolerance). Pooled as sums, so the
per-record fields carry kept / n counts.

Unneeded double stop: an onset t in an output part at which >= 2 output notes of that part sound,
whose pitch set does NOT sound together within one source part at t. Counted once per (part, t).

Weighted fidelity (the reward's F_w, for each approved weight setting): sum_tier w * kept /
sum_tier w * n.
"""
from __future__ import annotations

import bisect
from collections import defaultdict
from fractions import Fraction

from arrangement.eval.record import Score

TOL = Fraction(1, 4)
TIERS = ("top", "inner", "bass")
WEIGHTS = {"A": {"top": 1.0, "bass": 0.8, "inner": 0.25},   # BLOCK4.md 2b settings
           "B": {"top": 1.0, "bass": 1.0, "inner": 0.7},
           "C": {"top": 1.0, "bass": 1.0, "inner": 1.0}}


def voice_tiers(notes) -> list[str]:
    """Tier per note of `notes` ((part, onset, dur, pitch), dur > 0), in the given order."""
    order = sorted(range(len(notes)), key=lambda i: notes[i][1])
    out = [""] * len(notes)
    active: list[int] = []
    k = 0
    while k < len(order):
        t = notes[order[k]][1]
        new = []
        while k < len(order) and notes[order[k]][1] == t:
            new.append(order[k]); k += 1
        active = [j for j in active if notes[j][1] + notes[j][2] > t] + new
        px = [notes[j][3] for j in active]
        hi, lo = max(px), min(px)
        for i in new:
            x = notes[i][3]
            if len(active) == 1 or x >= hi:
                out[i] = "top"
            elif x <= lo:
                out[i] = "bass"
            else:
                out[i] = "inner"
    return out


def _sounding_sets(notes):
    """Per part: (sorted onsets, notes sorted by onset, max duration) for sounding-set queries."""
    by = defaultdict(list)
    for p, o, d, x in notes:
        if d > 0:
            by[p].append((o, o + d, x))
    res = {}
    for p, ns in by.items():
        ns.sort()
        res[p] = ([n[0] for n in ns], ns, max(n[1] - n[0] for n in ns))
    return res


def _sounding(idx, t):
    ons, ns, maxd = idx
    k = bisect.bisect_right(ons, t)
    out = set()
    while k > 0 and ns[k - 1][0] > t - maxd:
        k -= 1
        if ns[k][1] > t:
            out.add(ns[k][2])
    return out


def double_stops(out: Score, src: Score) -> dict:
    sidx = _sounding_sets(src.notes)
    per_part = defaultdict(list)
    for p, o, d, x in out.notes:
        if d > 0:
            per_part[p].append((o, o + d, x))
    ev = un = 0
    by_part = defaultdict(int)
    for p, ns in per_part.items():
        ns.sort()
        active, k = [], 0
        for t in sorted({n[0] for n in ns}):
            while k < len(ns) and ns[k][0] <= t:
                active.append(ns[k]); k += 1
            active = [n for n in active if n[1] > t]
            if len(active) < 2:
                continue
            ev += 1
            pitches = {n[2] for n in active}
            if not any(pitches <= _sounding(ix, t) for ix in sidx.values()):
                un += 1
                by_part[p] += 1
    n_out = sum(1 for n in out.notes if n[2] > 0)
    n_src = sum(1 for n in src.notes if n[2] > 0)
    return {"double_stop_events": ev, "unneeded_double_stops": un,
            "unneeded_double_stops__per_100": 100 * un / n_out if n_out else None,
            "unneeded_double_stops__per_100_source": 100 * un / n_src if n_src else None,
            "unneeded_double_stops__by_part": [by_part.get(p, 0) for p in range(len(out.parts))]}


def retention(out: Score, src: Score) -> dict:
    sn = [n for n in src.notes if n[2] > 0]
    tiers = voice_tiers(sn)
    by = defaultdict(list)
    for _, o, d, x in out.notes:
        if d > 0:
            by[x].append(o)
    for v in by.values():
        v.sort()

    def kept(o, x):
        ys = by.get(x)
        if not ys:
            return False
        k = bisect.bisect_right(ys, o - TOL)      # first onset > o - TOL
        return k < len(ys) and ys[k] < o + TOL
    res: dict = {}
    k_t, n_t = defaultdict(int), defaultdict(int)
    k_p, n_p = defaultdict(int), defaultdict(int)
    for (p, o, d, x), t in zip(sn, tiers):
        hit = kept(o, x)
        n_t[t] += 1; k_t[t] += hit
        n_p[p] += 1; k_p[p] += hit
    for t in TIERS:
        res[f"retention__{t}"] = k_t[t] / n_t[t] if n_t[t] else None
        res[f"retention__{t}__kept"] = k_t[t]
        res[f"retention__{t}__n"] = n_t[t]
    res["retention__by_source_part"] = [k_p[p] / n_p[p] if n_p[p] else None for p in range(len(src.parts))]
    for s, w in WEIGHTS.items():
        den = sum(w[t] * n_t[t] for t in TIERS)
        res[f"weighted_fidelity__{s}"] = sum(w[t] * k_t[t] for t in TIERS) / den if den else None
    return res


def reduction_metrics(out: Score, src: Score) -> dict:
    return {**retention(out, src), **double_stops(out, src)}
