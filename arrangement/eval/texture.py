"""Texture and diversity metrics (the reward-hacking detectors). METRICS.md
section "Texture and diversity". Each function reads one Score; comparisons
against the source are made by computing the same function on the source.
Grace notes (duration 0) count as notes but never as sounding.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations

import numpy as np

from arrangement.eval.record import Score
from arrangement.instruments import Ensemble


def _sounding_profile(notes) -> list[tuple[Fraction, Fraction, int]]:
    """Piecewise-constant number of distinct sounding pitches: (start, end, count) segments."""
    delta: dict[Fraction, Counter] = defaultdict(Counter)
    for _, o, d, x in notes:
        if d > 0:
            delta[o][x] += 1
            delta[o + d][x] -= 1
    active: Counter = Counter()
    segs, ts = [], sorted(delta)
    for a, b in zip(ts, ts[1:]):
        for x, c in delta[a].items():
            active[x] += c
        segs.append((a, b, sum(1 for c in active.values() if c > 0)))
    return segs


def polyphony_rate(notes) -> float | None:
    """Share of sounding time with >= 2 distinct pitches sounding."""
    segs = [(a, b, k) for a, b, k in _sounding_profile(notes) if k > 0]
    total = sum(b - a for a, b, _ in segs)
    return None if total == 0 else float(sum(b - a for a, b, k in segs if k >= 2) / total)


def onset_sets(score: Score) -> list[set[Fraction]]:
    s = [set() for _ in score.parts]
    for p, o, _, _ in score.notes:
        s[p].add(o)
    return s


def rhythmic_independence(score: Score) -> float | None:
    """Mean over pairs of non-empty parts of 1 - Jaccard(onset sets). 0 = every pair
    rhythmically locked; None with fewer than two non-empty parts."""
    sets = [s for s in onset_sets(score) if s]
    if len(sets) < 2:
        return None
    return float(np.mean([1 - len(a & b) / len(a | b) for a, b in combinations(sets, 2)]))


def doubling_rate(score: Score) -> float | None:
    """Share of non-grace notes for which ANOTHER part has a note with the same onset and
    the same pitch class (unison or octave doubling)."""
    by = defaultdict(set)   # (onset, pitch class) -> parts
    ng = [n for n in score.notes if n[2] > 0]
    for p, o, _, x in ng:
        by[(o, x % 12)].add(p)
    if not ng:
        return None
    return float(np.mean([len(by[(o, x % 12)]) > 1 for p, o, _, x in ng]))


def per_part_counts(score: Score) -> list[int]:
    c = Counter(n[0] for n in score.notes)
    return [c.get(p, 0) for p in range(len(score.parts))]


def mean_duration(notes) -> float | None:
    d = [float(n[2]) for n in notes if n[2] > 0]
    return float(np.mean(d)) if d else None


def texture(out: Score, src: Score, ens: Ensemble, span: Fraction,
            reference_source_parts=None) -> dict:
    """span = length in quarter notes of the source material the output covers (density denominator)."""
    P = len(out.parts)
    parts = [[n for n in out.notes if n[0] == p] for p in range(P)]
    src_parts = [[n for n in src.notes if n[0] == s] for s in range(len(src.parts))]
    res: dict = {}
    res["polyphony_rate"] = polyphony_rate(out.notes)
    res["polyphony_rate__source"] = polyphony_rate(src.notes)
    res["polyphony_rate__per_part"] = [polyphony_rate(x) for x in parts]
    sp = float(span) if span > 0 else None
    res["note_density"] = len(out.notes) / sp if sp else None
    res["note_density__source"] = len(src.notes) / sp if sp else None
    res["note_density__per_part"] = [len(x) / sp if sp else None for x in parts]
    res["rhythmic_independence"] = rhythmic_independence(out)
    res["rhythmic_independence__source"] = rhythmic_independence(src)
    counts = per_part_counts(out)
    res["n_notes__per_part"] = counts
    res["n_notes__source_per_part"] = per_part_counts(src)
    res["note_ratio__total"] = len(out.notes) / len(src.notes) if src.notes else None
    if reference_source_parts is not None:
        refs = [sum(res["n_notes__source_per_part"][s] for s in r) for r in reference_source_parts]
        res["note_ratio__per_part"] = [c / r if r else None for c, r in zip(counts, refs)]
        sd = [mean_duration([n for s in r for n in src_parts[s]]) for r in reference_source_parts]
        md = [mean_duration(x) for x in parts]
        res["duration_ratio__per_part"] = [a / b if a is not None and b else None for a, b in zip(md, sd)]
    else:
        res["note_ratio__per_part"] = None
        res["duration_ratio__per_part"] = None
    res["mean_duration"] = mean_duration(out.notes)
    res["mean_duration__source"] = mean_duration(src.notes)
    res["duration_ratio__total"] = (res["mean_duration"] / res["mean_duration__source"]
                                    if res["mean_duration"] is not None and res["mean_duration__source"] else None)
    res["pitch_std__per_part"] = [float(np.std([n[3] for n in x])) if x else None for x in parts]
    edge = []
    for p, x in enumerate(parts):
        inst = ens.instruments[p]
        d = [min(n[3] - inst.low, inst.high - n[3]) for n in x]
        edge.append({"mean": float(np.mean(d)) if d else None, "min": int(min(d)) if d else None,
                     "p05": float(np.percentile(d, 5)) if d else None,
                     "share_within_2": float(np.mean([0 <= v <= 2 for v in d])) if d else None})
    res["range_edge_distance__per_part"] = edge
    res["doubling_rate"] = doubling_rate(out)
    res["doubling_rate__source"] = doubling_rate(src)
    return res


# ------------------------------------------------------------ across seeds

def seed_pairwise(scores: list[Score], bars) -> dict:
    """Output diversity across seeds of one input: mean pairwise Note F1 and Note_i F1
    (paper definitions, segment-averaged) between every pair of seed outputs."""
    from arrangement.eval.fidelity import reference_metrics
    if len(scores) < 2:
        return {"n_seeds": len(scores), "pairwise_note_f1": None, "pairwise_note_i_f1": None}
    a, b = [], []
    for x, y in combinations(scores, 2):
        m = reference_metrics(x, y, bars)
        a.append(m["note_f1"]); b.append(m["note_i_f1"])
    a = [v for v in a if v is not None]; b = [v for v in b if v is not None]
    return {"n_seeds": len(scores), "pairwise_note_f1": float(np.mean(a)) if a else None,
            "pairwise_note_i_f1": float(np.mean(b)) if b else None}
