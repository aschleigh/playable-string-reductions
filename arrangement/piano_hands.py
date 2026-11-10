"""Piano hand assignment and soft keyboard measures (R83). Display and reporting only: the checker chooses no hands.

assign_hands(notes): notes [(onset, dur, pitch)] -> hand per note (0 right, 1 left). Onsets in time order; at each, the
struck notes split contiguously (low part left hand), keeping every held note in the hand that struck it:
  1. fewest pairs closer than GAP semitones between a left-hand note and a right-hand note (struck or held);
  2. smallest larger struck span per hand; 3. least movement of each hand's centre; 4. split nearest middle C.
soft_measures(notes, hands): per hand,
  fast_chords      3+-note chords struck within an 8th of the same hand's previous 3+-note chord, per 100 chords
  alternation      share of a hand's consecutive struck events that alternate chord / single note
  pinky_cluster    3+-note chords whose inner notes sit in the outer third on the pinky side (RH top, LH bottom)
  thumb_cluster    ... on the thumb side; per 100 3+-note chords
  gap_violations   onsets where a left-hand note (struck or held) is within GAP semitones of a right-hand note
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction as F

GAP = 3
FAST = F(1, 2)


def assign_hands(notes, fingers: int = 5):
    by_on = defaultdict(list)
    for i, (o, d, x) in enumerate(notes):
        by_on[o].append(i)
    hand = [0] * len(notes)
    held: list[int] = []
    centre = {0: 67.0, 1: 48.0}
    for o in sorted(by_on):
        held = [j for j in held if notes[j][0] + notes[j][1] > o and notes[j][0] < o]
        ids = sorted(by_on[o], key=lambda i: notes[i][2])
        ps = [notes[i][2] for i in ids]
        hl = [notes[j][2] for j in held if hand[j] == 1]
        hr = [notes[j][2] for j in held if hand[j] == 0]
        best = None
        for k in range(len(ps) + 1):
            lo, hi = ps[:k], ps[k:]
            over = max(len(lo) - fingers, len(hi) - fingers, 0)
            L, R = lo + hl, hi + hr
            close = sum(1 for a in L for b in R if b - a < GAP)
            span = max(lo[-1] - lo[0] if lo else 0, hi[-1] - hi[0] if hi else 0)
            move = sum(abs(sum(h) / len(h) - centre[c]) for c, h in ((1, lo), (0, hi)) if h)
            cut = (ps[k - 1] + ps[k]) / 2 if 0 < k < len(ps) else (ps[0] - 0.5 if k == 0 else ps[-1] + 0.5)
            cand = (over, close, span, move, abs(cut - 60))
            if best is None or cand < best[0]:
                best = (cand, k)
        k = best[1]
        for j, i in enumerate(ids):
            hand[i] = 1 if j < k else 0
        for c, h in ((1, ps[:k]), (0, ps[k:])):
            if h:
                centre[c] = sum(h) / len(h)
        held += ids
    return hand


def soft_measures(notes, hands):
    ev = {0: defaultdict(list), 1: defaultdict(list)}
    for (o, d, x), h in zip(notes, hands):
        ev[h][o].append(x)
    out = {}
    for h, name in ((0, "rh"), (1, "lh")):
        ons = sorted(ev[h])
        chords = [o for o in ons if len(ev[h][o]) >= 3]
        fast = sum(1 for a, b in zip(chords, chords[1:]) if b - a <= FAST)
        alt = [(len(ev[h][a]) >= 2) != (len(ev[h][b]) >= 2) for a, b in zip(ons, ons[1:])]
        pinky = thumb = 0
        for o in chords:
            ps = sorted(ev[h][o]); lo, hi = ps[0], ps[-1]
            if hi == lo:
                continue
            pos = [(x - lo) / (hi - lo) for x in ps[1:-1]]
            m = sum(pos) / len(pos)
            top, bottom = m > 2 / 3, m < 1 / 3
            pinky += top if h == 0 else bottom
            thumb += bottom if h == 0 else top
        n = max(1, len(chords))
        out[name] = {"chords_3plus": len(chords), "fast_chords_per_100": 100 * fast / n,
                     "alternation": sum(alt) / len(alt) if alt else 0.0,
                     "pinky_cluster_per_100": 100 * pinky / n, "thumb_cluster_per_100": 100 * thumb / n}
    gv = 0
    for o in sorted({n[0] for n in notes}):
        snd = [(x, h) for (a, d, x), h in zip(notes, hands) if a <= o < a + d]
        L = [x for x, h in snd if h == 1]; R = [x for x, h in snd if h == 0]
        gv += bool(L and R and min(R) - max(L) < GAP)
    out["gap_violations"] = gv
    out["onsets"] = len({n[0] for n in notes})
    return out
