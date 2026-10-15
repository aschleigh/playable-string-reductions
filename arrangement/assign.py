"""Rule-based assigners: notes -> parts. Neither consults the checker.

naive
    Pitch range only. Each part owns a fixed pitch band derived from the
    configured instrument ranges; a note goes to the part whose band holds
    its pitch. No time context at all. This is the validation ceiling.

continuity
    The naive bands plus a preference for keeping each part's line
    continuous. Notes are processed one onset slice at a time; each slice is
    one min-cost assignment of its notes to parts, with per-note cost
        w_band * semitones outside the part's band
      + w_cont * semitones from the part's most recent pitch(es)
      + w_busy * (notes the part is already sounding + notes already given
                  to it in this slice)
    The busy term favours one new note per part per slice and spreading
    chords across parts, without forbidding double stops.
    crossing = "forbid" (default): the slice's notes, sorted by pitch, are
    split into contiguous blocks in band order (V1 >= V2 >= Va >= Vc within
    a slice); exhaustive over the C(n+P-1, P-1) splits. crossing = "allow":
    unconstrained min-cost matching (scipy). On the dev split, "allow" makes
    the continuity term useless (best w_cont = 0); see results/assigner/.
    Grace notes sharing an onset with real notes join the part of the
    nearest-pitch real note. Weights live in
    config/assigner.yaml, tuned for label accuracy (not checker output).

Bands: parts are grouped by identical configured range and ordered by range
centre (high to low; ties by part order). Adjacent groups meet at the
midpoint of their centres. A group of g identical instruments (the two
violins) splits its band evenly, top sub-band to the lowest part index. The
outermost bands extend to +/- infinity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from functools import lru_cache
from itertools import combinations_with_replacement

import numpy as np
import yaml
from scipy.optimize import linear_sum_assignment

from arrangement.checker.types import NoteArrays
from arrangement.instruments import CONFIG_DIR, Ensemble

DEFAULT_CONFIG = CONFIG_DIR / "assigner.yaml"


@dataclass(frozen=True)
class ContinuityParams:
    w_band: float
    w_cont: float
    w_busy: float
    crossing: str = "forbid"     # "forbid" | "allow"

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> ContinuityParams:
        d = yaml.safe_load(Path(path).read_text())["continuity"]
        return cls(float(d["w_band"]), float(d["w_cont"]), float(d["w_busy"]), str(d.get("crossing", "forbid")))


def bands(ensemble: Ensemble) -> list[tuple[float, float]]:
    """[(lo, hi)) pitch band per part index."""
    insts = ensemble.instruments
    groups: dict[tuple[int, int], list[int]] = {}
    for p, inst in enumerate(insts):
        groups.setdefault((inst.low, inst.high), []).append(p)
    order = sorted(groups.items(), key=lambda kv: (-(kv[0][0] + kv[0][1]) / 2, kv[1][0]))
    centres = [(lo + hi) / 2 for (lo, hi), _ in order]
    out: dict[int, tuple[float, float]] = {}
    for k, ((lo, hi), members) in enumerate(order):
        top = (centres[k - 1] + centres[k]) / 2 if k > 0 else np.inf
        bot = (centres[k] + centres[k + 1]) / 2 if k + 1 < len(order) else -np.inf
        eff_top, eff_bot = min(top, hi), max(bot, lo)   # finite span to split among members
        g = len(members)
        cuts = [eff_top - (eff_top - eff_bot) * j / g for j in range(g + 1)]
        for j, p in enumerate(members):
            out[p] = (bot if j == g - 1 else cuts[j + 1], top if j == 0 else cuts[j])
    return [out[p] for p in range(len(insts))]


def _band_distance(pitch: np.ndarray, bands_: list[tuple[float, float]]) -> np.ndarray:
    """(n, P) semitones outside each part's band; 0 inside."""
    lo = np.array([b[0] for b in bands_])
    hi = np.array([b[1] for b in bands_])
    x = pitch[:, None].astype(float)
    return np.maximum(lo - x, 0) + np.maximum(x - hi, 0)


@lru_cache(maxsize=None)
def _splits(n: int, P: int) -> np.ndarray:
    """All boundary vectors 0 = b_0 <= b_1 <= ... <= b_P = n, shape (S, P+1)."""
    cuts = np.array(list(combinations_with_replacement(range(n + 1), P - 1)), dtype=np.int64).reshape(-1, P - 1)
    return np.hstack([np.zeros((len(cuts), 1), np.int64), cuts, np.full((len(cuts), 1), n, np.int64)])


def _ordered_slice(base: np.ndarray, busy: np.ndarray, w_busy: float, part_order: list[int]) -> np.ndarray:
    """base: (n, P) costs for notes sorted high->low. Returns part per note,
    notes split into contiguous blocks following part_order (high band first)."""
    n, P = base.shape
    b = _splits(n, P)                                        # (S, P+1)
    pref = np.vstack([np.zeros(P), np.cumsum(base, axis=0)])  # (n+1, P)
    total = np.zeros(len(b))
    for k, p in enumerate(part_order):
        lo, hi = b[:, k], b[:, k + 1]
        m = hi - lo
        total += pref[hi, p] - pref[lo, p] + w_busy * (m * busy[p] + m * (m - 1) / 2)
    best = b[int(np.argmin(total))]                          # argmin: first minimum, deterministic
    out = np.empty(n, dtype=np.int64)
    for k, p in enumerate(part_order):
        out[best[k]:best[k + 1]] = p
    return out


def naive(notes: NoteArrays, ensemble: Ensemble) -> np.ndarray:
    bs = bands(ensemble)
    out = np.empty(len(notes), dtype=np.int64)
    for p, (lo, hi) in enumerate(bs):
        out[(notes.pitch >= lo) & (notes.pitch < hi)] = p
    return out


def continuity(notes: NoteArrays, ensemble: Ensemble, params: ContinuityParams | None = None) -> np.ndarray:
    params = params or ContinuityParams.load()
    bs = bands(ensemble)
    P = len(ensemble)
    insts = ensemble.instruments
    # Initial "previous pitch" per part: centre of its finite band span.
    last: list[list[int]] = []
    for p, (lo, hi) in enumerate(bs):
        lo_f, hi_f = max(lo, insts[p].low), min(hi, insts[p].high)
        last.append([int(round((lo_f + hi_f) / 2))])
    band_cost = _band_distance(notes.pitch, bs)
    out = np.full(len(notes), -1, dtype=np.int64)
    sounding: list[list[int]] = [[] for _ in range(P)]   # end ticks of non-grace notes per part

    part_order = sorted(range(P), key=lambda p: (-bs[p][0], p))   # high band first
    # within a slice: pitch high -> low (ties by id)
    order = np.lexsort((np.arange(len(notes)), -notes.pitch, notes.onset))
    on = notes.onset[order]
    starts = np.flatnonzero(np.r_[True, on[1:] != on[:-1]])
    ends = np.r_[starts[1:], len(order)]
    for s, e in zip(starts, ends):
        slice_idx = order[s:e]
        t = int(on[s])
        g = notes.grace[slice_idx]
        idx = slice_idx[~g] if (~g).any() else slice_idx
        for p in range(P):
            sounding[p] = [x for x in sounding[p] if x > t]
        n = len(idx)
        busy = np.array([len(sounding[p]) for p in range(P)], dtype=float)
        pitch = notes.pitch[idx].astype(float)
        cont = np.stack([np.min(np.abs(pitch[:, None] - np.array(last[p])[None, :]), axis=1) for p in range(P)], axis=1)
        base = params.w_band * band_cost[idx] + params.w_cont * cont           # (n, P)
        if params.crossing == "forbid":
            parts = _ordered_slice(base, busy, params.w_busy, part_order)
        elif params.crossing == "allow":
            # Rows in ascending pitch. Ties between equal-cost matchings are
            # common here and resolved by row order: descending order instead
            # costs ~10 points of dev accuracy (results/assigner/README.md).
            rev = np.arange(n)[::-1]
            base, idx = base[rev], idx[rev]
            slots = np.arange(n, dtype=float)
            cost = (base[:, :, None] + params.w_busy * (busy[None, :, None] + slots[None, None, :])).reshape(n, P * n)
            rows, cols = linear_sum_assignment(cost)
            parts = np.empty(n, dtype=np.int64)
            parts[rows] = cols // n
        else:
            raise ValueError(f"crossing must be 'forbid' or 'allow', got {params.crossing!r}")
        new_last: dict[int, list[int]] = {}
        for r in range(n):
            p = int(parts[r])
            i = int(idx[r])
            out[i] = p
            new_last.setdefault(p, []).append(int(notes.pitch[i]))
            if not notes.grace[i]:
                sounding[p].append(int(notes.end[i]))
        # Grace notes sharing an onset with real notes follow the nearest-pitch
        # real note of the slice (ties: lower pitch, then lower id).
        if len(idx) < len(slice_idx):
            for i in slice_idx[g]:
                j = min(idx.tolist(), key=lambda j: (abs(int(notes.pitch[j]) - int(notes.pitch[i])), int(notes.pitch[j]), j))
                out[i] = out[j]
        for p, ps in new_last.items():
            last[p] = ps
    return out


ASSIGNERS = {"naive": naive, "continuity": continuity}
