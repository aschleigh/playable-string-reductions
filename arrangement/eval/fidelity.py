"""Fidelity metrics. METRICS.md section "Fidelity".

Published (Ou et al., arXiv 2408.15176v5, Section 4.3 and Appendix C.1),
implemented from the paper's equations, not from the released code:
  note_f1     match iff |t_x - t_y| < delta_t and p_x = p_y            (eq. 2-5)
  note_i_f1   ... and i_x = i_y                                       (eq. 6)
  mel_f1      Note F1 between the highest-average-pitch tracks          (eq. 7-8)
  i_iou       |I_out & I_tgt| / |I_out | I_tgt|                         (eq. 9)
  delta_t = one 16th note. Every metric is computed per segment (segment =
  one bar of the source, the paper's band-arrangement segment) and averaged
  arithmetically over segments.
Additions (ours, labelled as such everywhere):
  mel_top_f1  Note F1 between the ensemble top voices (skylines).
  harmony     per-beat pitch-class agreement with the source (cosine).
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

import numpy as np

from arrangement.eval.record import Note, Score

DELTA_T = Fraction(1, 4)   # one 16th note, in quarter notes
BEAT = Fraction(1)         # harmony beat = one quarter note


# ------------------------------------------------------------ matching

def _matches(xs: list[Fraction], ys: list[Fraction]) -> int:
    """Maximum one-to-one matching of two sorted onset lists under |x - y| < DELTA_T.
    Greedy two-pointer is optimal for points on a line with a symmetric window."""
    i = j = m = 0
    while i < len(xs) and j < len(ys):
        if abs(xs[i] - ys[j]) < DELTA_T:
            m += 1; i += 1; j += 1
        elif xs[i] < ys[j]:
            i += 1
        else:
            j += 1
    return m


def match_count(x: list[tuple], y: list[tuple]) -> int:
    """x, y = (onset, *key) tuples; notes match iff keys are equal and onsets within DELTA_T."""
    gx, gy = defaultdict(list), defaultdict(list)
    for t, *k in x:
        gx[tuple(k)].append(t)
    for t, *k in y:
        gy[tuple(k)].append(t)
    return sum(_matches(sorted(gx[k]), sorted(gy[k])) for k in gx.keys() & gy.keys())


def f1(n_match: int, n_x: int, n_y: int) -> float | None:
    """None when both sides are empty (segment excluded); 0 when exactly one is."""
    if n_x == 0 and n_y == 0:
        return None
    if n_match == 0:
        return 0.0
    p, r = n_match / n_x, n_match / n_y
    return 2 * p * r / (p + r)


# ------------------------------------------------------------ segments

def segment_notes(notes: tuple[Note, ...], bars) -> list[list[Note]]:
    """Notes grouped by the bar containing their onset (notes outside every bar are dropped)."""
    starts = [b[0] for b in bars]
    out: list[list[Note]] = [[] for _ in bars]
    for n in notes:
        k = _bar_of(starts, n[1])
        if k is not None and n[1] < bars[k][0] + bars[k][1]:
            out[k].append(n)
    return out


def _bar_of(starts, t):
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= t:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1 if lo else None


def melody_track(notes: list[Note]) -> list[Note]:
    """Eq. 7: the part with the highest mean pitch (ties: lower part index)."""
    by: dict[int, list[int]] = defaultdict(list)
    for p, _, _, x in notes:
        by[p].append(x)
    if not by:
        return []
    best = max(sorted(by), key=lambda p: np.mean(by[p]))
    return [n for n in notes if n[0] == best]


def skyline(notes: list[Note]) -> list[Note]:
    """Top voice (our addition): at each onset t, the highest note starting at t,
    kept unless a higher note is still sounding through t."""
    ng = [n for n in notes if n[2] > 0]
    by_t: dict[Fraction, Note] = {}
    for n in ng:
        if n[1] not in by_t or n[3] > by_t[n[1]][3]:
            by_t[n[1]] = n
    out = []
    for t, n in by_t.items():
        if not any(m[1] < t < m[1] + m[2] and m[3] > n[3] for m in ng):
            out.append(n)
    return out


def segment_scores(out: Score, tgt: Score, bars) -> dict[str, list[float]]:
    """Per-segment values of every reference-based metric (None segments dropped)."""
    so, st = segment_notes(out.notes, bars), segment_notes(tgt.notes, bars)
    oi, ti = out.instruments, tgt.instruments
    res: dict[str, list[float]] = {k: [] for k in ("note_f1", "note_i_f1", "mel_f1", "mel_top_f1", "i_iou")}
    for xo, xt in zip(so, st):
        a = [(n[1], n[3]) for n in xo]
        b = [(n[1], n[3]) for n in xt]
        ai = [(n[1], n[3], oi[n[0]]) for n in xo]
        bi = [(n[1], n[3], ti[n[0]]) for n in xt]
        ma, mb = melody_track(xo), melody_track(xt)
        sa, sb = skyline(xo), skyline(xt)
        vals = {
            "note_f1": f1(match_count(a, b), len(a), len(b)),
            "note_i_f1": f1(match_count(ai, bi), len(ai), len(bi)),
            "mel_f1": f1(match_count([(n[1], n[3]) for n in ma], [(n[1], n[3]) for n in mb]), len(ma), len(mb)),
            "mel_top_f1": f1(match_count([(n[1], n[3]) for n in sa], [(n[1], n[3]) for n in sb]), len(sa), len(sb)),
        }
        Io, It = {oi[n[0]] for n in xo}, {ti[n[0]] for n in xt}
        vals["i_iou"] = None if not (Io | It) else len(Io & It) / len(Io | It)
        for k, v in vals.items():
            if v is not None:
                res[k].append(v)
    return res


def reference_metrics(out: Score, tgt: Score, bars) -> dict:
    """Mean over segments, plus the segment count and sum so runs can be pooled
    exactly as the paper does (one mean over every segment of the test set)."""
    seg = segment_scores(out, tgt, bars)
    res = {}
    for k, v in seg.items():
        res[k] = float(np.mean(v)) if v else None
        res[f"{k}__n_segments"] = len(v)
        res[f"{k}__sum"] = float(np.sum(v))
    return res


# ------------------------------------------------------------ harmony (our addition)

def chroma_per_beat(notes: tuple[Note, ...], start: Fraction, end: Fraction) -> np.ndarray:
    """[n_beats, 12] duration-weighted pitch-class profile of each quarter-note beat in [start, end)."""
    n = max(0, int(np.ceil((end - start) / BEAT)))
    C = np.zeros((n, 12))
    for _, o, d, x in notes:
        if d == 0:
            continue
        a, b = max(o, start), min(o + d, end)
        if b <= a:
            continue
        k = int((a - start) // BEAT)
        while k < n:
            lo, hi = start + k * BEAT, start + (k + 1) * BEAT
            ov = min(b, hi) - max(a, lo)
            if ov <= 0:
                break
            C[k, x % 12] += float(ov)
            k += 1
    return C


def harmony_agreement(out: Score, src: Score, start: Fraction, end: Fraction) -> dict:
    """Mean cosine similarity of output and source beat chroma, over beats where the source sounds.
    A beat where the source sounds and the output is silent scores 0."""
    A, B = chroma_per_beat(out.notes, start, end), chroma_per_beat(src.notes, start, end)
    nb = np.linalg.norm(B, axis=1)
    na = np.linalg.norm(A, axis=1)
    m = nb > 0
    if not m.any():
        return {"harmony": None, "harmony__n_beats": 0, "harmony__sum": 0.0}
    cos = np.where(na[m] > 0, (A[m] * B[m]).sum(1) / np.maximum(na[m] * nb[m], 1e-300), 0.0)
    return {"harmony": float(cos.mean()), "harmony__n_beats": int(m.sum()), "harmony__sum": float(cos.sum())}
