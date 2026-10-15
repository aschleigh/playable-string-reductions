"""Training examples with labels for the three heads (part, octave, realisation).

Per input note the model predicts:
  part         index into the target ensemble's parts, or DROP
  octave       shift applied to the input pitch: -24, -12, 0, +12, +24
  realisation  PLAIN, TREMOLO, REPEAT, ARPEGGIATE, DOUBLE (closed vocabulary)
expand() turns (input notes, labels) into output notes. Ops:
  plain       the note as is
  repeat      repeated 8ths (the last absorbs any remainder; under a quarter: two equal halves)
  tremolo     repeated 16ths (likewise; under an 8th: two equal halves). For collapsed
              figuration (dur = n x the unit) this is exactly the original n notes.
  arpeggiate  all notes of one output part with the same onset, duration and label are played
              in ascending order, each dur / k (one note alone = plain)
  double      the note plus its upper octave

Label sources (make_example), every transformation reversible:
  1. Real string figuration in the TARGET is collapsed to its plain form in the INPUT, each
     detected instance independently with probability COLLAPSE_P; the inverse op is the label:
       repeat: >= 3 contiguous single notes, same pitch, all 1/2 long  -> one note, label REPEAT
       tremolo: the same with all 1/4 long                             -> one note, label TREMOLO
       arpeggio: 3-4 contiguous single notes, equal length, strictly ascending, every
                 interval >= 3 semitones                               -> block chord, ARPEGGIATE
       octave double stop: exactly two notes in the part at an onset, same length, 12 apart
                                                                       -> lower note, DOUBLE
  2. Keyboard idioms added to the INPUT:
       octave doubling (prob P_KBD_DOUBLE per window): a lower-octave copy of some top-part
       notes is added; the copies are labelled DROP
       register displacement (prob P_SHIFT per window): one source part is moved +-12 in the
       input; its notes are labelled with the inverse octave shift
  3. Target ensemble per window: quartet (true parts), trio (Vn1+Vn2 -> violin, Va, Vc) or duo
     (Vn1+Vn2 -> violin, Va+Vc -> cello). A note outside its target instrument's range gets
     the nearest octave shift that fits, else DROP; a unison duplicate in one target part
     keeps the longest copy and DROPs the others.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction as F

PLAIN, TREMOLO, REPEAT, ARPEGGIATE, DOUBLE = range(5)
REAL_NAMES = ["plain", "tremolo", "repeat", "arpeggiate", "double"]
OCTAVES = [-24, -12, 0, 12, 24]
DROP = -1

# instrument ranges = arrangement/config/instruments.yaml (copied by load_ranges at runtime)
ENSEMBLES = {
    "quartet": (["violin", "violin", "viola", "cello"], {0: 0, 1: 1, 2: 2, 3: 3}),
    "trio": (["violin", "viola", "cello"], {0: 0, 1: 0, 2: 1, 3: 2}),
    "duo": (["violin", "cello"], {0: 0, 1: 0, 2: 1, 3: 1}),
}
ENSEMBLE_P = {"quartet": 0.5, "trio": 0.3, "duo": 0.2}
COLLAPSE_P = 0.5
P_KBD_DOUBLE, KBD_DOUBLE_FRAC = 0.25, 0.2
P_SHIFT = 0.25
WINDOW, CONTEXT = F(16), F(8)


@dataclass
class INote:
    onset: F
    dur: F
    pitch: int
    part: int = DROP          # label
    octave: int = 0           # label, semitones
    real: int = PLAIN         # label
    context: bool = False     # in the context region (labels revealed)
    src: int = -1             # source part 0..3 (Vn1 Vn2 Va Vc); -1 = unknown. Input feature (arranger-v2)
    merged: bool = False      # decode v2: a unison duplicate merged into an earlier note of its part (no output)


def load_ranges() -> dict[str, tuple[int, int]]:
    from arrangement.instruments import load_instruments
    return {k: (v.low, v.high) for k, v in load_instruments().items()}


# ------------------------------------------------------------ detection (on one true part)

def detect(notes: list[tuple[F, F, int]]) -> list[tuple[int, list[int]]]:
    """Instances (kind, note indices) in one part's notes, sorted by onset. Disjoint."""
    by_on: dict[F, list[int]] = {}
    for i, (o, d, x) in enumerate(notes):
        by_on.setdefault(o, []).append(i)
    used: set[int] = set()
    out = []
    for o, ids in by_on.items():   # octave double stops
        if len(ids) == 2:
            a, b = sorted(ids, key=lambda i: notes[i][2])
            if notes[a][1] == notes[b][1] and notes[b][2] - notes[a][2] == 12:
                out.append((DOUBLE, [a, b])); used |= {a, b}
    single = [ids[0] for o, ids in sorted(by_on.items()) if len(ids) == 1 and ids[0] not in used]
    runs, cur = [], []
    for i in single:   # contiguous runs of single notes
        if cur and notes[cur[-1]][0] + notes[cur[-1]][1] == notes[i][0]:
            cur.append(i)
        else:
            if len(cur) >= 3:
                runs.append(cur)
            cur = [i]
    if len(cur) >= 3:
        runs.append(cur)
    for run in runs:
        k = 0
        while k < len(run):
            # repeated pitch
            j = k
            while j + 1 < len(run) and notes[run[j + 1]][2] == notes[run[k]][2] and notes[run[j + 1]][1] == notes[run[k]][1]:
                j += 1
            seg = run[k:j + 1]
            d = notes[run[k]][1]
            if len(seg) >= 3 and d in (F(1, 2), F(1, 4)):
                out.append((REPEAT if d == F(1, 2) else TREMOLO, seg)); k = j + 1; continue
            # ascending broken chord of 3-4
            m = k
            while (m + 1 < len(run) and m - k < 3 and notes[run[m + 1]][1] == d
                   and notes[run[m + 1]][2] - notes[run[m]][2] >= 3):
                m += 1
            if m - k + 1 >= 3:
                out.append((ARPEGGIATE, run[k:m + 1])); k = m + 1; continue
            k += 1
    return out


def collapse(kind: int, notes: list[tuple[F, F, int]], ids: list[int]) -> list[tuple[F, F, int, int]]:
    """Input notes (onset, dur, pitch, realisation label) replacing the instance."""
    if kind == DOUBLE:
        lo = min(ids, key=lambda i: notes[i][2])
        return [(notes[lo][0], notes[lo][1], notes[lo][2], DOUBLE)]
    o = notes[ids[0]][0]
    total = sum((notes[i][1] for i in ids), F(0))
    if kind in (REPEAT, TREMOLO):
        return [(o, total, notes[ids[0]][2], kind)]
    return [(o, total, notes[i][2], ARPEGGIATE) for i in ids]


# ------------------------------------------------------------ expansion

def expand(inotes: list[INote]) -> list[tuple[int, F, F, int]]:
    """Output notes (part, onset, dur, pitch) from labelled input notes."""
    out = []
    groups: dict[tuple, list[INote]] = {}
    for n in inotes:
        if n.part == DROP or n.merged:
            continue
        p = n.pitch + n.octave
        if n.real == ARPEGGIATE:
            groups.setdefault((n.part, n.onset, n.dur), []).append(n)
        elif n.real in (REPEAT, TREMOLO):
            sub = F(1, 2) if n.real == REPEAT else F(1, 4)
            if n.dur < 2 * sub:                       # too short to repeat: two equal halves
                out += [(n.part, n.onset, n.dur / 2, p), (n.part, n.onset + n.dur / 2, n.dur / 2, p)]
            else:                                     # notes of exactly `sub`, the last absorbs the rest
                k = int(n.dur // sub)
                out += [(n.part, n.onset + j * sub, sub, p) for j in range(k - 1)]
                out.append((n.part, n.onset + (k - 1) * sub, n.dur - (k - 1) * sub, p))
        elif n.real == DOUBLE:
            out += [(n.part, n.onset, n.dur, p), (n.part, n.onset, n.dur, p + 12)]
        else:
            out.append((n.part, n.onset, n.dur, p))
    for (part, o, d), g in groups.items():
        ps = sorted(n.pitch + n.octave for n in g)
        k = len(ps)
        out += [(part, o + j * d / k, d / k, x) for j, x in enumerate(ps)]
    return out


# ------------------------------------------------------------ examples

def make_example(notes: list[tuple[int, F, F, int]], start: F, rng: random.Random, ranges,
                 ensemble: str | None = None, augment: bool = True) -> tuple[str, list[INote], list]:
    """notes = (true part 0..3, onset, dur, pitch) of one movement. Window [start, start+WINDOW),
    context [start-CONTEXT, start). Returns (ensemble, input notes with labels, target notes)."""
    ens = ensemble or rng.choices(list(ENSEMBLE_P), weights=list(ENSEMBLE_P.values()))[0]
    insts, pmap = ENSEMBLES[ens]
    lo_t, hi_t = start - CONTEXT, start + WINDOW
    shift_part = rng.randrange(4) if augment and rng.random() < P_SHIFT else None
    shift = rng.choice([12, -12]) if shift_part is not None else 0
    inotes: list[INote] = []
    for sp in range(4):
        pn = sorted((o, d, x) for p, o, d, x in notes if p == sp and lo_t <= o < hi_t)
        coll = {}
        if augment:
            for kind, ids in detect(pn):
                if rng.random() < COLLAPSE_P:
                    coll[ids[0]] = (kind, ids)
        skip = {i for _, ids in coll.values() for i in ids}
        seq = [(o, d, x, PLAIN) for i, (o, d, x) in enumerate(pn) if i not in skip]
        for kind, ids in coll.values():
            seq += collapse(kind, pn, ids)
        for o, d, x, r in seq:
            s = shift if sp == shift_part and 21 <= x + shift <= 108 else 0
            inotes.append(INote(o, d, x + s, part=pmap[sp], octave=-s, real=r, context=o < start, src=sp))
    # fit target ranges (octave), else drop
    for n in inotes:
        lo, hi = ranges[insts[n.part]]
        tgt = n.pitch + n.octave
        top = tgt + (12 if n.real == DOUBLE else 0)
        if lo <= tgt and top <= hi:
            continue
        for extra in sorted((-24, -12, 12, 24), key=abs):
            if n.octave + extra in OCTAVES and lo <= tgt + extra and top + extra <= hi:
                n.octave += extra
                break
        else:
            n.part = DROP
    # unison duplicates within one target part: keep the longest
    seen: dict[tuple, INote] = {}
    for n in sorted(inotes, key=lambda n: -n.dur):
        if n.part == DROP:
            continue
        k = (n.part, n.onset, n.pitch + n.octave)
        if k in seen:
            n.part = DROP
        else:
            seen[k] = n
    # keyboard octave doubling in the input
    if augment and rng.random() < P_KBD_DOUBLE:
        top = [n for n in inotes if n.part == pmap[0] and n.pitch - 12 >= 21]
        for n in rng.sample(top, int(len(top) * KBD_DOUBLE_FRAC)):
            inotes.append(INote(n.onset, n.dur, n.pitch - 12, part=DROP, octave=0, real=PLAIN, context=n.context,
                                src=n.src))
    inotes.sort(key=lambda n: (n.onset, n.pitch, n.dur))
    target = expand(inotes)
    return ens, inotes, target
