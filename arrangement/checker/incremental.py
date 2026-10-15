"""Incremental hard-tier checker over a partial assignment.

State = an assignment note -> part (or unassigned). Unassigned notes are
invisible to every check, so a partial arrangement is checked by exactly the
same rules as a complete one. Each violation is stored under a key that
depends only on the notes involved, so the violation set is a pure function
of the assignment: commit order never matters (tested against checker.batch).

Rule definitions (shared with batch.py; see PLAN.md "Decisions"):
  sounding set S(p, t)   non-grace notes of part p with onset <= t < end.
  range        note pitch outside [low, high] of its part's instrument.
  simultaneity monophonic parts: every strictly overlapping non-grace pair.
  chord_size   at each onset t of a non-grace note in p: |S(p,t)| > max_chord.
  hand_span    keyboard parts, at each such t: S(p,t) has no split into a
               lower and an upper hand, each <= fingers notes and <= semitones
               wide (skipped when |S| > 2*fingers: that is chord size's job).
  transition   for every note c of p: the predecessors are the notes of p that
               were released last at or before c's onset (a grace note is not
               a predecessor of another grace note at the same onset). The leap
               is to the nearest predecessor pitch (ties: lower pitch, then
               lower id); gap = onset(c) - that release (time_basis
               "release") or - that predecessor's onset ("onset"). Violation when
               leap > max_leap_at_zero_gap + semitones_per_quarter_gap * gap.

checker-v2 adds multistop, bow, shift (strings), duplicate (polyphonic non-string
instruments) and hand_leap (keyboards); definitions in rules_v2.py. multistop,
bow and hand_leap are evaluated at onsets like chord_size; shift uses the
transition predecessor block; duplicate is pairwise like simultaneity.

Every check except transition, shift and hand_leap is monotone (assigning more notes never clears a
violation, though a chord-size/hand-span violation is replaced by its superset).
Transition is not: a later commit can supply a nearer or later predecessor.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right, insort

import numpy as np

from arrangement.instruments import Ensemble
from arrangement.checker import rules_v2 as R2
from arrangement.checker.types import UNASSIGNED, Delta, NoteArrays, Violation, canonical

_INF = float("inf")
_BIG = 1 << 62


def best_two_hand_span(pitches: list[int], fingers: int) -> int | None:
    """Smallest achievable max(lower-hand span, upper-hand span) over splits
    of the sorted pitches, or None if no split respects `fingers`."""
    n = len(pitches)
    best = None
    for k in range(n + 1):
        if k > fingers or n - k > fingers:
            continue
        lo = pitches[k - 1] - pitches[0] if k else 0
        hi = pitches[-1] - pitches[k] if k < n else 0
        worst = max(lo, hi)
        if best is None or worst < best:
            best = worst
    return best


class IncrementalChecker:
    def __init__(self, notes: NoteArrays, ensemble: Ensemble):
        self.notes = notes
        self.ensemble = ensemble
        self.n_parts = len(ensemble)
        self._on = notes.onset.tolist()
        self._end = notes.end.tolist()
        self._pitch = notes.pitch.tolist()
        self._grace = notes.grace.tolist()
        self._tpq = notes.tpq
        ng = ~notes.grace
        self._maxdur = int((notes.end[ng] - notes.onset[ng]).max()) if ng.any() else 0
        self.assign = np.full(len(notes), UNASSIGNED, dtype=np.int64)
        P = self.n_parts
        self._ng_on: list[list[tuple[int, int]]] = [[] for _ in range(P)]   # non-grace (onset, id)
        self._all_on: list[list[tuple[int, int]]] = [[] for _ in range(P)]  # all (onset, id)
        self._ends: list[list[tuple[int, int]]] = [[] for _ in range(P)]    # all (end, id)
        self._v: dict[tuple, Violation] = {}

    # ---------------------------------------------------------------- public
    def commit(self, i: int, part: int) -> Delta:
        if self.assign[i] != UNASSIGNED:
            raise ValueError(f"note {i} already assigned to part {self.assign[i]}")
        if not 0 <= part < self.n_parts:
            raise ValueError(f"part {part} out of range")
        self.assign[i] = part
        self._insert(i, part)
        keys = self._affected(i, part)
        old = {k: self._v.get(k) for k in keys}  # _v still holds the pre-commit values
        return self._apply(keys, old)

    def uncommit(self, i: int) -> Delta:
        part = int(self.assign[i])
        if part == UNASSIGNED:
            raise ValueError(f"note {i} is not assigned")
        keys = self._affected(i, part)
        old = {k: self._v.get(k) for k in keys}
        self.assign[i] = UNASSIGNED
        self._remove(i, part)
        return self._apply(keys, old)

    def would_violate(self, i: int, part: int) -> tuple[Violation, ...]:
        """Violations that committing (i, part) would add. State unchanged."""
        d = self.commit(i, part)
        self.uncommit(i)
        return d.added

    def mask(self, i: int) -> np.ndarray:
        """mask[p] True iff assigning note i to part p adds no violation."""
        return np.array([not self.would_violate(i, p) for p in range(self.n_parts)], dtype=bool)

    def violations(self) -> list[Violation]:
        return canonical(self._v.values())

    # ------------------------------------------------------------- internals
    def _insert(self, i: int, p: int) -> None:
        if not self._grace[i]:
            insort(self._ng_on[p], (self._on[i], i))
        insort(self._all_on[p], (self._on[i], i))
        insort(self._ends[p], (self._end[i], i))

    def _remove(self, i: int, p: int) -> None:
        for lst, t in ((self._all_on[p], self._on[i]), (self._ends[p], self._end[i])):
            del lst[bisect_left(lst, (t, i))]
        if not self._grace[i]:
            lst = self._ng_on[p]
            del lst[bisect_left(lst, (self._on[i], i))]

    def _apply(self, keys: list[tuple], old: dict) -> Delta:
        added, removed = [], []
        for k in keys:
            new = self._eval(k)
            o = old[k]
            if new == o:
                continue
            if o is not None:
                removed.append(o)
            if new is None:
                self._v.pop(k, None)
            else:
                self._v[k] = new
                added.append(new)
        return Delta(tuple(canonical(added)), tuple(canonical(removed)))

    def _affected(self, i: int, p: int) -> list[tuple]:
        """Keys whose value can depend on whether note i is in part p.
        Called while i is present in p."""
        inst = self.ensemble.instruments[p]
        keys: list[tuple] = [("range", i)]
        on_i, end_i = self._on[i], self._end[i]
        if not self._grace[i]:
            if inst.monophonic:
                for j in self._overlapping(p, on_i, end_i):
                    if j != i:
                        keys.append(("sim", p, min(i, j), max(i, j)))
            elif inst.strings is None:
                for j in self._overlapping(p, on_i, end_i):
                    if j != i and self._pitch[j] == self._pitch[i]:
                        keys.append(("dup", p, min(i, j), max(i, j)))
            if inst.max_chord is not None or inst.hand_span is not None or inst.hand_leap is not None:
                lst = self._ng_on[p]
                ts = {on_i}
                for k in range(bisect_left(lst, (on_i, -1)), bisect_left(lst, (end_i, -1))):
                    ts.add(lst[k][0])
                if inst.hand_leap is not None and inst.hand_span is not None:
                    k = bisect_right(lst, (on_i, _BIG))          # next onset after on_i
                    if k < len(lst):
                        ts.add(lst[k][0])
                    k = bisect_left(lst, (end_i, -1))            # first onset at or after end_i
                    if k < len(lst):
                        ts.add(lst[k][0])
                for t in sorted(ts):
                    if inst.max_chord is not None:
                        keys.append(("chord", p, t))
                    if inst.hand_span is not None:
                        keys.append(("hand", p, t))
                    if inst.strings is not None:
                        keys.append(("ms", p, t))
                        keys.append(("bow", p, t))
                        if inst.strings.triple_max_stretch is not None:
                            keys.append(("tonset", p, t))
                            keys.append(("tstretch", p, t))
                    if inst.hand_leap is not None and inst.hand_span is not None:
                        keys.append(("hleap", p, t))
                if inst.strings is not None and inst.strings.double_min_gap is not None:
                    for t in sorted(ts):
                        keys.append(("donset", p, t))
                        keys.append(("restrike", p, t))
                    hi = end_i + inst.strings.double_min_gap * self._tpq
                    for k in range(bisect_left(lst, (on_i, -1)), len(lst)):
                        if lst[k][0] >= hi:
                            break
                        keys.append(("drate", p, lst[k][0]))
                    keys.append(("drate", p, on_i))
                if inst.strings is not None and inst.strings.triple_min_gap is not None:
                    # 3+-note rate: sounding sets change on [on_i, end_i); a changed moment is
                    # the previous 3+-note moment of onsets up to min_gap later
                    hi = end_i + inst.strings.triple_min_gap * self._tpq
                    for k in range(bisect_left(lst, (on_i, -1)), len(lst)):
                        if lst[k][0] >= hi:
                            break
                        keys.append(("trate", p, lst[k][0]))
                    keys.append(("trate", p, on_i))
                if inst.strings is not None and inst.strings.triple_recover is not None:
                    # checker-v5: a 3+-note moment depends on its sounding set (onsets in [on_i, end_i)) and on
                    # its next onset (moments up to `recover` before on_i)
                    lo = on_i - inst.strings.triple_recover * self._tpq
                    for k in range(bisect_left(lst, (lo, -1)), len(lst)):
                        if lst[k][0] >= end_i:
                            break
                        keys.append(("trecov", p, lst[k][0]))
                    keys.append(("trecov", p, on_i))
        if inst.transition is not None or inst.strings is not None:
            keys.append(("trans", p, i))
            # Notes whose predecessor block can include i: onset in [end_i, E),
            # E = first non-grace release after end_i (later notes see E first).
            ends = self._ends[p]
            E = _BIG
            for k in range(bisect_right(ends, (end_i, _BIG)), len(ends)):
                if not self._grace[ends[k][1]]:
                    E = ends[k][0]
                    break
            lst = self._all_on[p]
            for k in range(bisect_left(lst, (end_i, -1)), bisect_left(lst, (E, -1))):
                c = lst[k][1]
                if c != i:
                    keys.append(("trans", p, c))
        if inst.strings is not None:
            keys += [("shift",) + k[1:] for k in keys if k[0] == "trans"]
        if inst.transition is None:
            keys = [k for k in keys if k[0] != "trans"]
        return keys

    def _overlapping(self, p: int, a: int, b: int) -> list[int]:
        """Non-grace notes of p strictly overlapping [a, b)."""
        lst = self._ng_on[p]
        out = []
        for k in range(bisect_left(lst, (a - self._maxdur, -1)), bisect_left(lst, (b, -1))):
            j = lst[k][1]
            if self._end[j] > a:
                out.append(j)
        return out

    def _sounding(self, p: int, t: int) -> list[int]:
        lst = self._ng_on[p]
        out = []
        for k in range(bisect_left(lst, (t - self._maxdur, -1)), bisect_right(lst, (t, _BIG))):
            j = lst[k][1]
            if self._end[j] > t:
                out.append(j)
        return out

    def _has_onset(self, p: int, t: int) -> bool:
        lst = self._ng_on[p]
        k = bisect_left(lst, (t, -1))
        return k < len(lst) and lst[k][0] == t

    def _eval(self, key: tuple) -> Violation | None:
        kind = key[0]
        if kind == "range":
            i = key[1]
            p = int(self.assign[i])
            if p == UNASSIGNED:
                return None
            inst = self.ensemble.instruments[p]
            x = self._pitch[i]
            if x < inst.low:
                return Violation("range", p, (i,), float(x), float(inst.low))
            if x > inst.high:
                return Violation("range", p, (i,), float(x), float(inst.high))
            return None
        if kind == "sim":
            _, p, i, j = key
            if self.assign[i] != p or self.assign[j] != p:
                return None
            ov = min(self._end[i], self._end[j]) - max(self._on[i], self._on[j])
            if ov <= 0:
                return None
            return Violation("simultaneity", p, (i, j), ov / self._tpq, 0.0)
        if kind in ("chord", "hand"):
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            S = sorted(self._sounding(p, t))
            inst = self.ensemble.instruments[p]
            if kind == "chord":
                if len(S) > inst.max_chord:
                    return Violation("chord_size", p, tuple(S), float(len(S)), float(inst.max_chord))
                return None
            hs = inst.hand_span
            if len(S) < 2 or len(S) > 2 * hs.fingers:
                return None
            best = best_two_hand_span(sorted(self._pitch[j] for j in S), hs.fingers)
            if best is not None and best > hs.semitones:
                return Violation("hand_span", p, tuple(S), float(best), float(hs.semitones))
            return None
        if kind == "trans":
            _, p, c = key
            if self.assign[c] != p:
                return None
            return self._transition(p, c)
        if kind == "dup":
            _, p, i, j = key
            if self.assign[i] != p or self.assign[j] != p:
                return None
            ov = min(self._end[i], self._end[j]) - max(self._on[i], self._on[j])
            if ov <= 0:
                return None
            return Violation("duplicate", p, (i, j), ov / self._tpq, 0.0)
        if kind in ("ms", "bow"):
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            S = sorted(self._sounding(p, t))
            sp = self.ensemble.instruments[p].strings
            if kind == "ms":
                if not 2 <= len(S) <= len(sp.open):
                    return None
                ok, st = R2.placement(tuple(sorted(self._pitch[j] for j in S)), sp.open, sp.max_offset, sp.max_stretch)
                return None if ok else Violation("multistop", p, tuple(S), min(st, 99.0), float(sp.max_stretch))
            lim = sp.bow_sustain_max_dur * self._tpq
            long_ = [j for j in S if self._end[j] - self._on[j] > lim]
            if len(long_) <= sp.bow_max_sustained:
                return None
            return Violation("bow", p, tuple(S), float(len(long_)), float(sp.bow_max_sustained))
        if kind in ("donset", "restrike", "drate"):
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            S = sorted(self._sounding(p, t))
            sp = self.ensemble.instruments[p].strings
            if len(S) < 2:
                return None
            if kind == "donset":
                if len(S) != 2:            # 3+ notes: triple_onset
                    return None
                late = sum(1 for j in S if self._on[j] != t)
                return Violation("double_onset", p, tuple(S), float(late), 0.0) if late else None
            if kind == "restrike":
                held = {self._pitch[j] for j in S if self._on[j] != t}
                new = [j for j in S if self._on[j] == t and self._pitch[j] in held]
                if not new:
                    return None
                return Violation("restrike", p, tuple(S), float(len(new)), 0.0)
            lst = self._ng_on[p]
            k = bisect_left(lst, (t, -1)) - 1
            while k >= 0:                     # latest earlier onset with 2+ sounding notes
                t0 = lst[k][0]
                if (t - t0) >= sp.double_min_gap * self._tpq:
                    return None
                S0 = self._sounding(p, t0)
                if len(S0) >= 2:
                    if sorted(self._pitch[j] for j in S0) == sorted(self._pitch[j] for j in S):
                        return None           # the same double stop repeated: bow only, no new fingering
                    return Violation("double_rate", p, tuple(sorted(set(S0) | set(S))), (t - t0) / self._tpq,
                                     float(sp.double_min_gap))
                k = bisect_left(lst, (t0, -1)) - 1
            return None
        if kind == "trecov":                  # checker-v5
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            S = sorted(self._sounding(p, t))
            if len(S) < 3:
                return None
            sp = self.ensemble.instruments[p].strings
            lst = self._ng_on[p]
            k = bisect_right(lst, (t, _BIG))
            if k < len(lst) and lst[k][0] - t < sp.triple_recover * self._tpq:
                t1 = lst[k][0]
                ids = tuple(sorted(set(S) | {j for o, j in lst[bisect_left(lst, (t1, -1)):bisect_right(lst, (t1, _BIG))]}))
                return Violation("triple_recover", p, ids, (t1 - t) / self._tpq, float(sp.triple_recover))
            return None
        if kind in ("tonset", "tstretch", "trate"):
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            S = sorted(self._sounding(p, t))
            sp = self.ensemble.instruments[p].strings
            if len(S) < 3:
                return None
            if kind == "tonset":
                late = sum(1 for j in S if self._on[j] != t)
                return Violation("triple_onset", p, tuple(S), float(late), 0.0) if late else None
            if kind == "tstretch":
                if len(S) > len(sp.open):
                    return None
                ok, st = R2.placement(tuple(sorted(self._pitch[j] for j in S)), sp.open, sp.max_offset,
                                      sp.triple_max_stretch)
                return None if ok else Violation("triple_stretch", p, tuple(S), min(st, 99.0),
                                                 float(sp.triple_max_stretch))
            lst = self._ng_on[p]
            k = bisect_left(lst, (t, -1)) - 1
            while k >= 0:                     # latest earlier onset with 3+ sounding notes
                t0 = lst[k][0]
                if (t - t0) >= sp.triple_min_gap * self._tpq:
                    return None
                S0 = self._sounding(p, t0)
                if len(S0) >= 3:
                    return Violation("triple_rate", p, tuple(sorted(set(S0) | set(S))), (t - t0) / self._tpq,
                                     float(sp.triple_min_gap))
                k = bisect_left(lst, (t0, -1)) - 1
            return None
        if kind == "hleap":
            _, p, t = key
            if not self._has_onset(p, t):
                return None
            lst = self._ng_on[p]
            k = bisect_left(lst, (t, -1)) - 1
            if k < 0:
                return None
            t0 = lst[k][0]
            inst = self.ensemble.instruments[p]
            hs, hl = inst.hand_span, inst.hand_leap
            A = tuple(sorted(self._pitch[j] for j in self._sounding(p, t0)))
            B = tuple(sorted(self._pitch[j] for j in self._sounding(p, t)))
            move = R2.hand_move(A, B, hs.fingers, hs.semitones)
            allowed = hl.allowed((t - t0) / self._tpq)
            if move == float("inf") or move <= allowed:
                return None
            ids = tuple(sorted(set(self._sounding(p, t0)) | set(self._sounding(p, t))))
            return Violation("hand_leap", p, ids, float(move), float(allowed))
        if kind == "shift":
            _, p, c = key
            if self.assign[c] != p:
                return None
            return self._shift(p, c)
        raise KeyError(key)

    def _block(self, p: int, c: int) -> list[int]:
        """Transition predecessor block of c (notes of p released last at or before c's onset)."""
        on_c, gc = self._on[c], self._grace[c]
        ends = self._ends[p]
        k = bisect_right(ends, (on_c, _BIG)) - 1
        M, out = None, []
        while k >= 0:
            e, a = ends[k]
            if M is not None and e < M:
                break
            k -= 1
            if a == c or (gc and self._grace[a] and self._on[a] == on_c):
                continue
            M = e
            out.append(a)
        return out

    def _shift(self, p: int, c: int) -> Violation | None:
        sp = self.ensemble.instruments[p].strings
        lim = sp.shift_min_time * self._tpq
        best = None   # (move, id)
        for a in self._block(p, c):
            m = R2.shift(self._pitch[a], self._pitch[c], sp.open, sp.max_offset) \
                if self._on[c] - self._on[a] < lim else 0
            if best is None or (m, a) < best:
                best = (m, a)
        if best is None or best[0] <= sp.shift_max_semitones:
            return None
        return Violation("shift", p, (best[1], c), float(best[0]), float(sp.shift_max_semitones))

    def _transition(self, p: int, c: int) -> Violation | None:
        on_c, pc, gc = self._on[c], self._pitch[c], self._grace[c]
        ends = self._ends[p]
        k = bisect_right(ends, (on_c, _BIG)) - 1
        M = None
        best = None  # (dist, pitch, id)
        while k >= 0:
            e, a = ends[k]
            if M is not None and e < M:
                break
            k -= 1
            if a == c or (gc and self._grace[a] and self._on[a] == on_c):
                continue
            M = e
            pa = self._pitch[a]
            cand = (abs(pc - pa), pa, a)
            if best is None or cand < best:
                best = cand
        if best is None:
            return None
        tr = self.ensemble.instruments[p].transition
        ref = M if tr.time_basis == "release" else self._on[best[2]]
        allowed = tr.allowed((on_c - ref) / self._tpq)
        if best[0] > allowed:
            return Violation("transition", p, (best[2], c), float(best[0]), float(allowed))
        return None
