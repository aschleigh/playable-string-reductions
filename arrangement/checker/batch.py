"""Full-assignment checker (vectorized). Same rules as incremental.py, written
independently so the two can be tested against each other."""
from __future__ import annotations

import numpy as np

from arrangement.instruments import Ensemble, InstrumentDef
from arrangement.checker import rules_v2 as R2
from arrangement.checker.incremental import best_two_hand_span
from arrangement.checker.types import UNASSIGNED, NoteArrays, Violation, canonical


def check(notes: NoteArrays, ensemble: Ensemble, assignment: np.ndarray) -> list[Violation]:
    """Violations of `assignment` (part index per note, -1 = unassigned)."""
    assignment = np.asarray(assignment, dtype=np.int64)
    if assignment.shape != (len(notes),):
        raise ValueError("assignment must have one entry per note")
    if ((assignment < UNASSIGNED) | (assignment >= len(ensemble))).any():
        raise ValueError("assignment holds an invalid part index")
    out: list[Violation] = []
    for p, inst in enumerate(ensemble.instruments):
        idx = np.flatnonzero(assignment == p)
        if len(idx):
            out += _part(notes, p, inst, idx)
    return canonical(out)


def _part(notes: NoteArrays, p: int, inst: InstrumentDef, idx: np.ndarray) -> list[Violation]:
    out: list[Violation] = []
    tpq = notes.tpq
    pitch = notes.pitch[idx]

    for i in idx[pitch < inst.low]:
        out.append(Violation("range", p, (int(i),), float(notes.pitch[i]), float(inst.low)))
    for i in idx[pitch > inst.high]:
        out.append(Violation("range", p, (int(i),), float(notes.pitch[i]), float(inst.high)))

    ng = idx[~notes.grace[idx]]
    if len(ng):
        ng = ng[np.lexsort((ng, notes.onset[ng]))]
        on, en = notes.onset[ng], notes.end[ng]

        if inst.monophonic:
            # sorted by onset: b after a overlaps a iff onset_b < end_a
            hi = np.searchsorted(on, en, side="left")
            for a in np.flatnonzero(hi > np.arange(len(ng)) + 1):
                for b in range(a + 1, hi[a]):
                    i, j = int(ng[a]), int(ng[b])
                    ov = min(en[a], en[b]) - max(on[a], on[b])
                    out.append(Violation("simultaneity", p, (min(i, j), max(i, j)), ov / tpq, 0.0))

        if inst.max_chord is not None or inst.hand_span is not None:
            ts = np.unique(on)
            cnt = np.searchsorted(on, ts, side="right") - np.searchsorted(np.sort(en), ts, side="right")
            if inst.max_chord is not None:
                for t, c in zip(ts[cnt > inst.max_chord], cnt[cnt > inst.max_chord]):
                    S = tuple(sorted(int(x) for x in ng[(on <= t) & (en > t)]))
                    out.append(Violation("chord_size", p, S, float(c), float(inst.max_chord)))
            hs = inst.hand_span
            if hs is not None:
                sel = (cnt >= 2) & (cnt <= 2 * hs.fingers)
                for t in ts[sel]:
                    S = tuple(sorted(int(x) for x in ng[(on <= t) & (en > t)]))
                    best = best_two_hand_span(sorted(int(notes.pitch[j]) for j in S), hs.fingers)
                    if best is not None and best > hs.semitones:
                        out.append(Violation("hand_span", p, S, float(best), float(hs.semitones)))

    if inst.transition is not None:
        out += _transitions(notes, p, inst, idx)
    out += _v2(notes, p, inst, idx)
    return out


def _v2(notes: NoteArrays, p: int, inst: InstrumentDef, idx: np.ndarray) -> list[Violation]:
    """checker-v2 rules (rules_v2.py), straightforward reference loops."""
    out: list[Violation] = []
    tpq = notes.tpq
    il = idx.tolist()
    on = dict(zip(il, notes.onset[idx].tolist()))
    en = dict(zip(il, notes.end[idx].tolist()))
    px = dict(zip(il, notes.pitch[idx].tolist()))
    gr = dict(zip(il, notes.grace[idx].tolist()))
    ng = [i for i in il if not gr[i]]
    onsets = sorted({on[i] for i in ng})
    sp, hs, hl = inst.strings, inst.hand_span, inst.hand_leap
    sounding: dict[int, list[int]] = {}
    if sp is not None or hl is not None:     # sweep over onsets
        starts = sorted(ng, key=lambda i: on[i])
        active: set[int] = set()
        k = 0
        for t in onsets:
            while k < len(starts) and on[starts[k]] <= t:
                active.add(starts[k]); k += 1
            active = {i for i in active if en[i] > t}
            sounding[t] = sorted(active)
    if not inst.monophonic and sp is None:      # duplicate
        by_pitch: dict[int, list[int]] = {}
        for i in ng:
            by_pitch.setdefault(px[i], []).append(i)
        for ids in by_pitch.values():
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    i, j = ids[a], ids[b]
                    ov = min(en[i], en[j]) - max(on[i], on[j])
                    if ov > 0:
                        out.append(Violation("duplicate", p, (min(i, j), max(i, j)), ov / tpq, 0.0))
    if sp is not None:
        for t in onsets:
            S = sounding[t]
            if 2 <= len(S) <= len(sp.open):
                ok, st = R2.placement(tuple(sorted(px[j] for j in S)), sp.open, sp.max_offset, sp.max_stretch)
                if not ok:
                    out.append(Violation("multistop", p, tuple(S), min(st, 99.0), float(sp.max_stretch)))
            long_ = [j for j in S if en[j] - on[j] > sp.bow_sustain_max_dur * tpq]
            if len(long_) > sp.bow_max_sustained:
                out.append(Violation("bow", p, tuple(S), float(len(long_)), float(sp.bow_max_sustained)))
        if sp.double_min_gap is not None:              # checker-v4
            prev2 = None
            for t in onsets:
                S = sounding[t]
                if len(S) < 2:
                    continue
                if len(S) == 2:
                    late = sum(1 for j in S if on[j] != t)
                    if late:
                        out.append(Violation("double_onset", p, tuple(S), float(late), 0.0))
                held = {px[j] for j in S if on[j] != t}
                new = [j for j in S if on[j] == t and px[j] in held]
                if new:
                    out.append(Violation("restrike", p, tuple(S), float(len(new)), 0.0))
                if (prev2 is not None and t - prev2 < sp.double_min_gap * tpq
                        and sorted(px[j] for j in sounding[prev2]) != sorted(px[j] for j in S)):
                    out.append(Violation("double_rate", p, tuple(sorted(set(sounding[prev2]) | set(S))),
                                         (t - prev2) / tpq, float(sp.double_min_gap)))
                prev2 = t
        if sp.triple_max_stretch is not None:          # checker-v3
            prev3 = None
            nxt = dict(zip(onsets, onsets[1:] + [None]))   # checker-v5: next non-grace onset in the part
            for t in onsets:
                S = sounding[t]
                if len(S) < 3:
                    continue
                late = sum(1 for j in S if on[j] != t)
                if late:
                    out.append(Violation("triple_onset", p, tuple(S), float(late), 0.0))
                if len(S) <= len(sp.open):
                    ok, st = R2.placement(tuple(sorted(px[j] for j in S)), sp.open, sp.max_offset,
                                          sp.triple_max_stretch)
                    if not ok:
                        out.append(Violation("triple_stretch", p, tuple(S), min(st, 99.0),
                                             float(sp.triple_max_stretch)))
                if sp.triple_min_gap is not None and prev3 is not None and t - prev3 < sp.triple_min_gap * tpq:
                    out.append(Violation("triple_rate", p, tuple(sorted(set(sounding[prev3]) | set(S))),
                                         (t - prev3) / tpq, float(sp.triple_min_gap)))
                if sp.triple_recover is not None and nxt[t] is not None and nxt[t] - t < sp.triple_recover * tpq:
                    ids = tuple(sorted(set(S) | {j for j in sounding[nxt[t]] if on[j] == nxt[t]}))   # chord + next notes
                    out.append(Violation("triple_recover", p, ids, (nxt[t] - t) / tpq, float(sp.triple_recover)))
                prev3 = t
        lim = sp.shift_min_time * tpq
        from bisect import bisect_right
        rel_sorted = sorted((en[a], a) for a in il)
        ends_only = [e for e, _ in rel_sorted]
        for c in il:
            k = bisect_right(ends_only, on[c]) - 1
            block, M = [], None
            while k >= 0:
                e, a = rel_sorted[k]
                if M is not None and e < M:
                    break
                k -= 1
                if a == c or (gr[c] and gr[a] and on[a] == on[c]):
                    continue
                M = e
                block.append(a)
            if not block:
                continue
            m, a = min(((R2.shift(px[a], px[c], sp.open, sp.max_offset) if on[c] - on[a] < lim else 0), a)
                       for a in block)
            if m > sp.shift_max_semitones:
                out.append(Violation("shift", p, (a, c), float(m), float(sp.shift_max_semitones)))
    if hl is not None and hs is not None:
        for t0, t in zip(onsets, onsets[1:]):
            A, B = sounding[t0], sounding[t]
            move = R2.hand_move(tuple(sorted(px[j] for j in A)), tuple(sorted(px[j] for j in B)),
                                hs.fingers, hs.semitones)
            allowed = hl.allowed((t - t0) / tpq)
            if move != float("inf") and move > allowed:
                out.append(Violation("hand_leap", p, tuple(sorted(set(A) | set(B))), float(move), float(allowed)))
    return out


def _nearest(key, sp, first_of_run, lo, hi, M, pitch):
    """Vectorized nearest-pitch predecessor within blocks [lo, hi) of arrays
    sorted by (end, pitch, id) whose end is M. Ties: lower pitch, then lower id."""
    pos = np.clip(np.searchsorted(key, M * 128 + pitch, side="left"), lo, hi)
    has_up, has_dn = pos < hi, pos > lo
    up = np.where(has_up, pos, lo)
    dn = np.where(has_dn, first_of_run[np.maximum(pos - 1, 0)], lo)
    big = np.iinfo(np.int64).max
    d_up = np.where(has_up, sp[up] - pitch, big)
    d_dn = np.where(has_dn, pitch - sp[dn], big)
    take_dn = d_dn <= d_up
    return np.where(take_dn, dn, up), np.where(take_dn, d_dn, d_up)


def _sorted_block_arrays(notes: NoteArrays, ids: np.ndarray):
    order = ids[np.lexsort((ids, notes.pitch[ids], notes.end[ids]))]   # by (end, pitch, id)
    se, sp = notes.end[order], notes.pitch[order]
    key = se * 128 + sp
    return order, se, sp, key, np.searchsorted(key, key, side="left")


def _transitions(notes: NoteArrays, p: int, inst: InstrumentDef, idx: np.ndarray) -> list[Violation]:
    tr = inst.transition
    tpq = notes.tpq
    order, se, sp, key, first_of_run = _sorted_block_arrays(notes, idx)
    c_on, c_pitch, c_grace = notes.onset[idx], notes.pitch[idx], notes.grace[idx]
    preds, leaps, Ms, cs = [], [], [], []

    # Non-grace c: every note released at or before its onset is valid; the
    # block is the notes with the latest such release.
    f = np.flatnonzero(~c_grace)
    hi = np.searchsorted(se, c_on[f], side="right")
    f, hi = f[hi > 0], hi[hi > 0]
    if len(f):
        M = se[hi - 1]
        lo = np.searchsorted(se, M, side="left")
        pr, lp = _nearest(key, sp, first_of_run, lo, hi, M, c_pitch[f])
        preds.append(order[pr]); leaps.append(lp); Ms.append(M); cs.append(idx[f])

    # Grace c at onset t: other grace notes at t (which also end at t) are not
    # predecessors. Valid block = non-grace notes released exactly at t if any,
    # else all notes with the latest release strictly before t.
    g = np.flatnonzero(c_grace)
    if len(g):
        t = c_on[g]
        ng_ids = idx[~c_grace]
        n_order, n_se, n_sp, n_key, n_first = _sorted_block_arrays(notes, ng_ids)
        a_lo = np.searchsorted(n_se, t, side="left")
        a_hi = np.searchsorted(n_se, t, side="right")
        A = a_hi > a_lo
        if A.any():
            pr, lp = _nearest(n_key, n_sp, n_first, a_lo[A], a_hi[A], t[A], c_pitch[g[A]])
            preds.append(n_order[pr]); leaps.append(lp); Ms.append(t[A]); cs.append(idx[g[A]])
        b = g[~A]
        b_hi = np.searchsorted(se, c_on[b], side="left")          # all releases strictly before t
        b, b_hi = b[b_hi > 0], b_hi[b_hi > 0]
        if len(b):
            M = se[b_hi - 1]
            lo = np.searchsorted(se, M, side="left")
            pr, lp = _nearest(key, sp, first_of_run, lo, b_hi, M, c_pitch[b])
            preds.append(order[pr]); leaps.append(lp); Ms.append(M); cs.append(idx[b])

    out: list[Violation] = []
    if not preds:
        return out
    pred, leap, M, c = (np.concatenate(x) for x in (preds, leaps, Ms, cs))
    ref = M if tr.time_basis == "release" else notes.onset[pred]
    gap = (notes.onset[c] - ref) / tpq
    allowed = tr.max_leap_at_zero_gap + tr.semitones_per_quarter_gap * gap
    for k in np.flatnonzero(leap > allowed):
        out.append(Violation("transition", p, (int(pred[k]), int(c[k])),
                             float(leap[k]), float(tr.allowed(float(gap[k])))))
    return out
