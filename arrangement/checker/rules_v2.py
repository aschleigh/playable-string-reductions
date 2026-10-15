"""Rule functions added in checker-v2 (agreed 2026-10-08). Pure functions of
pitches / times, shared by the batch and incremental checkers.

Strings (instruments with a `strings` block): each note is placed on a string;
offset = semitones above that string's open pitch, valid in 0..max_offset
(max_offset = range.high - top open string). Offset 0 = open string, which
needs no finger.

  multistop  notes sounding together (2..n_strings of them) need a placement with
             one note per string, the strings used adjacent (the bow cannot skip a
             string), and the stopped notes within one hand position:
             max offset - min offset over stopped notes <= max_stretch.
             The same pitch on two strings is allowed (unison double stop).
  bow        at most `bow_max_sustained` sounding notes may be longer than
             `bow_sustain_max_dur` (3- and 4-note chords only short or broken).
  shift      consecutive notes (the transition predecessor block): the hand move
             = min over string choices of |offset change| (0 if either note is an
             open string), minimised over the block; violation when the move exceeds
             `shift.max_semitones` and the time from the predecessor's onset is
             below `shift.min_time`.
  triple_*   checker-v3, at every onset where 3+ notes sound in a string part:
             triple_onset   all of them must start at that onset (struck together);
             triple_stretch placement within triple.max_stretch (tighter than max_stretch);
             triple_rate    the previous such onset is >= triple.min_gap quarters earlier.
  double_*   checker-v4, at every onset where 2+ notes sound in a string part:
             double_onset   exactly 2 sounding: both must start at that onset (no held note
                            under or over a new one; 3+ is triple_onset);
             restrike       a new note may not repeat a pitch that is still sounding;
             double_rate    the previous 2+-note onset is >= double.min_gap quarters earlier,
                            unless it holds the same pitches (a repeated double stop needs no new fingering).
Other instruments:
  duplicate  polyphonic non-string instruments: the same pitch sounding twice at
             once in one part (one key cannot be struck twice).
  hand_leap  keyboards: between consecutive onsets, the smallest hand movement over
             two-hand splits of both sounding sets (each hand <= fingers notes and
             <= span), movement = |change of a hand's mean pitch|, empty hand = 0;
             violation when it exceeds max_leap_at_zero_gap + per_quarter * gap.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations


@lru_cache(maxsize=200_000)
def placement(pitches: tuple[int, ...], open_: tuple[int, ...], max_offset: int, max_stretch: int) -> tuple[bool, float]:
    """(feasible, best stretch over valid one-note-per-adjacent-string placements;
    inf if no such placement exists)."""
    n, S = len(pitches), len(open_)
    best = float("inf")
    if n > S:
        return False, best
    for lo in range(S - n + 1):                      # contiguous block of strings
        strings = range(lo, lo + n)
        for perm in permutations(strings):
            offs = [p - open_[s] for p, s in zip(pitches, perm)]
            if any(o < 0 or o > max_offset for o in offs):
                continue
            stopped = [o for o in offs if o > 0]
            st = (max(stopped) - min(stopped)) if len(stopped) > 1 else 0
            best = min(best, st)
            if best == 0:
                return True, 0.0
    return best <= max_stretch, float(best)


@lru_cache(maxsize=200_000)
def shift(pa: int, pc: int, open_: tuple[int, ...], max_offset: int) -> int:
    """Smallest hand move between two consecutive notes over string choices."""
    best = None
    oa = [pa - o for o in open_ if 0 <= pa - o <= max_offset]
    oc = [pc - o for o in open_ if 0 <= pc - o <= max_offset]
    if not oa or not oc:
        return 0   # unplaceable notes are the range check's business
    for a in oa:
        for c in oc:
            m = 0 if a == 0 or c == 0 else abs(a - c)
            best = m if best is None else min(best, m)
    return best


def _hands(ps: tuple[int, ...], fingers: int, span: int):
    """Contiguous two-hand splits of sorted pitches that respect fingers and span."""
    n = len(ps)
    for k in range(n + 1):
        lo, hi = ps[:k], ps[k:]
        if len(lo) > fingers or len(hi) > fingers:
            continue
        if (lo and lo[-1] - lo[0] > span) or (hi and hi[-1] - hi[0] > span):
            continue
        yield lo, hi


def _centre(h):
    return sum(h) / len(h) if h else None


@lru_cache(maxsize=200_000)
def hand_move(a: tuple[int, ...], b: tuple[int, ...], fingers: int, span: int) -> float:
    """Smallest max(left move, right move) between two sounding sets; inf if either
    set has no valid split (hand_span's business, not counted twice: callers skip)."""
    best = float("inf")
    for la, ha in _hands(a, fingers, span):
        for lb, hb in _hands(b, fingers, span):
            m = 0.0
            for x, y in ((la, lb), (ha, hb)):
                cx, cy = _centre(x), _centre(y)
                if cx is not None and cy is not None:
                    m = max(m, abs(cy - cx))
            best = min(best, m)
    return best
