"""Block 6 rule-built supervised targets (BLOCK6.md Step 2, R63): F (solo flute) and K (solo piano).

    python -m model.targets_fk [--regimes flute piano] [--workers 16] [--limit N] [--tag T]
        -> model/results/rl/targets_fk{tag}__{split}.pkl  {key: {"flute"|"piano": [(part, octave, realisation)]}}

Notes are visited as in S2 (model/targets_s2.py): time order, then source voice tier (top, bass, inner), then
pitch, highest first. Each takes the first option the frozen checker accepts (the decoder's Committer, masked,
unisons merged); labels are plain realisation.

F (flute; ensemble solo_flute, monophonic, C4-C7):
  1. top-tier notes: octave 0, then +12, -12, +24, -24 (into range, monophonic); else drop.
  2. (weaving needs no rule: the top tier is a skyline, a note at or above everything sounding when it starts,
     so the line already moves to the next-highest voice when the first violin rests; R64)
  3. breath (soft): after BREATH_RUN quarters of continuous playing (no rest of an eighth or more), the next short
     note (<= an eighth) before a boundary (a leap of a fifth or more, or a note of a quarter or longer) is
     dropped, leaving a breath. The labels cannot shorten a note, so a breath is a dropped short note (R64).
  4. everything else is dropped.
K (piano; ensemble piano, one part, the checker splits the hands):
  1. every note: octave 0; then an octave toward the middle (C4); then, for top and bass notes only, the other
     direction; else drop (so inner voices go first).
K2 (R82, targets_fk3; the user: K "quite thick", too many chords over an octave, split between the hands): K under
checker-v7 (hand span 12) with two thinning rules:
  2. an inner note whose pitch class is already kept among the notes struck at its onset (a doubling) is dropped;
  3. at most K2_FINGERS notes struck together per hand (the targets' own cap; the checker still allows five).
K3 (R83, targets_fk4; the pianist: thickness is fine): K under checker-v8 (hands a minor third apart, 9ths/10ths after
a set-up time), with two soft tie-breakers for inner notes only:
  4. among the octave options, those that do not bunch the inner notes of the hand's chord toward the pinky (RH top,
     LH bottom; arrangement/piano_hands) are tried first;
  5. an inner note that would make a third 3+-note chord in a row in the same hand, each within an 8th, is dropped
     (chord / single alternation is preferred in fast passages).
"""
from __future__ import annotations

import argparse
import pickle
from collections import Counter
from fractions import Fraction as F
from multiprocessing import Pool

import model.augment as A
from arrangement.instruments import load_ensemble
from model.decode import TIER_RANK, Committer
from model.grpo import RL, load_split

REGIMES = ("flute", "piano")
ENSEMBLE = {"flute": "solo_flute", "piano": "piano"}
BREATH_RUN = F(8)     # quarters (BLOCK6 decision 2)
BREATH_MAX = F(12)    # breath v2 (R67): a breath is forced by then
EIGHTH = F(1, 2)
PIANO_K2 = False      # set by --piano-k2 (fork workers inherit it)
PIANO_K3 = False      # set by --piano-k3


def _order(m):
    return sorted(range(len(m.src)), key=lambda i: (m.src[i][1], TIER_RANK[m.tiers[i]], -m.src[i][3]))


def build_flute(m, stats, breath: int = 1):
    ens = load_ensemble(ENSEMBLE["flute"])
    inst = ens.instruments[0]
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    for i in _order(m):
        x = m.src[i][3]
        if m.tiers[i] != "top":
            inotes[i].part = A.DROP
            stats["drop_other"] += 1
            continue
        for s in (0, 12, -12, 24, -24):
            if inst.low <= x + s <= inst.high and com.try_commit(i, inotes, 0, s, A.PLAIN):
                stats[f"top_oct{s:+d}"] += 1
                break
        else:
            inotes[i].part = A.DROP
            stats["drop_top"] += 1
    # breath (soft): drop a short note at a boundary after a long continuous run
    kept = sorted((m.src[i][1], i) for i, n in enumerate(inotes) if n.part != A.DROP and not n.merged)
    if breath == 2:
        _breath_v2(m, inotes, kept, stats)
    else:
        _breath_v1(m, inotes, kept, stats)
    return [(n.part, n.octave, n.real) for n in inotes]


def _breath_v1(m, inotes, kept, stats):
    """v1 (control-J): only a short note (<= an eighth) just before a boundary, once BREATH_RUN is reached."""
    run_start, prev_end = None, None
    for k, (o, i) in enumerate(kept):
        if prev_end is None or o - prev_end >= EIGHTH:
            run_start = o
        d = m.src[i][2]
        if o - run_start >= BREATH_RUN and d <= EIGHTH and k + 1 < len(kept):
            j = kept[k + 1][1]
            leap = abs((m.src[j][3] + inotes[j].octave) - (m.src[i][3] + inotes[i].octave))
            if leap >= 7 or m.src[j][2] >= 1:
                inotes[i].part = A.DROP          # removing a note never makes a monophonic line infeasible
                stats["breath"] += 1
                run_start, prev_end = None, None
                continue
        prev_end = o + d if prev_end is None else max(prev_end, o + d)


def _breath_v2(m, inotes, kept, stats):
    """v2 (R67): after BREATH_RUN quarters, prefer a short note (<= an eighth) before a boundary; failing that, the
    shortest note (<= a quarter) in the next 4 quarters; at BREATH_MAX quarters, the next note of <= a quarter."""
    run_start, prev_end, k = None, None, 0
    while k < len(kept):
        o, i = kept[k]
        if prev_end is None or o - prev_end >= EIGHTH:
            run_start = o
        d = m.src[i][2]
        pick = None
        if o - run_start >= BREATH_RUN and k + 1 < len(kept):
            j = kept[k + 1][1]
            leap = abs((m.src[j][3] + inotes[j].octave) - (m.src[i][3] + inotes[i].octave))
            if d <= EIGHTH and (leap >= 7 or m.src[j][2] >= 1):
                pick = k
            elif o - run_start >= BREATH_RUN + 4 or o - run_start >= BREATH_MAX:
                ahead = [q for q in range(k, len(kept)) if kept[q][0] < o + 4 and m.src[kept[q][1]][2] <= 1]
                if ahead:
                    pick = min(ahead, key=lambda q: (m.src[kept[q][1]][2], kept[q][0])) if o - run_start < BREATH_MAX else ahead[0]
        if pick is not None:
            inotes[kept[pick][1]].part = A.DROP
            stats["breath"] += 1
            run_start, prev_end = None, None
            k = pick + 1
            continue
        prev_end = o + d if prev_end is None else max(prev_end, o + d)
        k += 1


def build_flute_cut(m, stats):
    """F3 (R70, targets_fk2): the F rules with the CUT realisation. A melody note that would overlap the next melody note
    is labelled CUT (it ends where the next begins) instead of losing one of the pair; a breath is a CUT (an eighth
    shorter) on a note of a quarter or more at a boundary, once BREATH_RUN quarters have passed without a rest; if none
    comes by BREATH_MAX, the next note in the following 4 quarters that can be shortened is CUT, else the shortest
    note there is dropped."""
    ens = load_ensemble(ENSEMBLE["flute"])
    inst = ens.instruments[0]
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    A.assign_cut_ends(inotes, m.tiers)
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    for i in _order(m):
        x = m.src[i][3]
        if m.tiers[i] != "top":
            inotes[i].part = A.DROP
            stats["drop_other"] += 1
            continue
        real = A.CUT if inotes[i].cut_kind == "overlap" else A.PLAIN
        for s in (0, 12, -12, 24, -24):
            if inst.low <= x + s <= inst.high and com.try_commit(i, inotes, 0, s, real):
                stats[f"top_oct{s:+d}"] += 1
                stats["cut_overlap"] += real == A.CUT
                break
        else:
            inotes[i].part = A.DROP
            stats["drop_top"] += 1
    kept = sorted((m.src[i][1], i) for i, n in enumerate(inotes) if n.part != A.DROP and not n.merged)
    end_of = lambda i: inotes[i].cut_end if inotes[i].real == A.CUT else m.src[i][1] + m.src[i][2]
    run_start, prev_end, k = None, None, 0
    while k < len(kept):
        o, i = kept[k]
        if prev_end is None or o - prev_end >= EIGHTH:
            run_start = o
        if o - run_start >= BREATH_RUN:
            boundary = k + 1 < len(kept) and (abs((m.src[kept[k + 1][1]][3] + inotes[kept[k + 1][1]].octave)
                                                  - (m.src[i][3] + inotes[i].octave)) >= 7 or m.src[i][2] >= 2)
            if inotes[i].real == A.PLAIN and inotes[i].cut_kind == "breath" and (boundary or o - run_start >= BREATH_MAX):
                inotes[i].real = A.CUT                   # an eighth shorter: shortening never breaks a monophonic line
                stats["breath_cut"] += 1
                run_start, prev_end, k = None, None, k + 1
                continue
            if o - run_start >= BREATH_MAX:
                ahead = [q for q in range(k, len(kept)) if kept[q][0] < o + 4]
                cuts = [q for q in ahead if inotes[kept[q][1]].real == A.PLAIN and inotes[kept[q][1]].cut_kind == "breath"]
                if cuts:                                 # first: shorten the next note that can be shortened
                    inotes[kept[cuts[0]][1]].real = A.CUT
                    stats["breath_cut_late"] += 1
                    run_start, prev_end, k = None, None, cuts[0] + 1
                    continue
                if ahead:                                # else: drop the shortest note in the next 4 quarters
                    q = min(ahead, key=lambda q: (m.src[kept[q][1]][2], kept[q][0]))
                    inotes[kept[q][1]].part = A.DROP
                    stats["breath_drop"] += 1
                    run_start, prev_end, k = None, None, q + 1
                    continue
        e = end_of(i)
        prev_end = e if prev_end is None else max(prev_end, e)
        k += 1
    return [(n.part, n.octave, n.real) for n in inotes]


def build_piano(m, stats):
    ens = load_ensemble(ENSEMBLE["piano"])
    inst = ens.instruments[0]
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    for i in _order(m):
        x, tier = m.src[i][3], m.tiers[i]
        mid = 12 if x < 60 else -12
        opts = [0, mid] + ([-mid] if tier in ("top", "bass") else [])
        for s in opts:
            if inst.low <= x + s <= inst.high and com.try_commit(i, inotes, 0, s, A.PLAIN):
                stats[f"{tier}_oct{s:+d}"] += 1
                break
        else:
            inotes[i].part = A.DROP
            stats[f"drop_{tier}"] += 1
    return [(n.part, n.octave, n.real) for n in inotes]


K2_FINGERS = 4


def build_piano_k2(m, stats):
    from dataclasses import replace
    ens = load_ensemble(ENSEMBLE["piano"])
    inst = ens.instruments[0]
    assert inst.hand_span.semitones == 12, "K2 targets are built under checker-v7 (hand span 12)"
    ens = replace(ens, instruments=(replace(inst, hand_span=replace(inst.hand_span, fingers=K2_FINGERS)),))
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    struck_pc = {}                                           # onset -> pitch classes kept (sounding pitch)
    for i in _order(m):
        o, x, tier = m.src[i][1], m.src[i][3], m.tiers[i]
        if tier == "inner" and x % 12 in struck_pc.get(o, ()):
            inotes[i].part = A.DROP
            stats["drop_inner_doubling"] += 1
            continue
        mid = 12 if x < 60 else -12
        opts = [0, mid] + ([-mid] if tier in ("top", "bass") else [])
        for s in opts:
            if inst.low <= x + s <= inst.high and com.try_commit(i, inotes, 0, s, A.PLAIN):
                stats[f"{tier}_oct{s:+d}"] += 1
                struck_pc.setdefault(o, set()).add((x + s) % 12)
                break
        else:
            inotes[i].part = A.DROP
            stats[f"drop_{tier}"] += 1
    return [(n.part, n.octave, n.real) for n in inotes]


def _split(ps, fingers=5):
    """Contiguous split of sorted pitches into (left, right): smallest larger span, ties nearest middle C."""
    best = None
    for k in range(len(ps) + 1):
        over = max(k - fingers, len(ps) - k - fingers, 0)
        span = max(ps[k - 1] - ps[0] if k else 0, ps[-1] - ps[k] if k < len(ps) else 0)
        cut = (ps[k - 1] + ps[k]) / 2 if 0 < k < len(ps) else (ps[0] - 0.5 if k == 0 else ps[-1] + 0.5)
        c = (over, span, abs(cut - 60))
        if best is None or c < best[0]:
            best = (c, k)
    return ps[: best[1]], ps[best[1]:]


def _hand_of(ps, x):
    lo, hi = _split(sorted(ps))
    return (lo, 1) if x in lo else (hi, 0)


def _pinky(chord, h):
    if len(chord) < 3 or chord[-1] == chord[0]:
        return False
    m = sum((x - chord[0]) / (chord[-1] - chord[0]) for x in chord[1:-1]) / (len(chord) - 2)
    return m > 2 / 3 if h == 0 else m < 1 / 3


def build_piano_k3(m, stats):
    ens = load_ensemble(ENSEMBLE["piano"])
    inst = ens.instruments[0]
    assert inst.hand_span.gap is not None, "K3 targets are built under checker-v8"
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    struck = {}                                              # onset -> kept sounding pitches
    for i in _order(m):
        o, x, tier = m.src[i][1], m.src[i][3], m.tiers[i]
        mid = 12 if x < 60 else -12
        opts = [0, mid] + ([-mid] if tier in ("top", "bass") else [])
        opts = [s_ for s_ in opts if inst.low <= x + s_ <= inst.high]
        if tier == "inner" and opts:
            now = struck.get(o, [])
            ch, h = _hand_of(now + [x + opts[0]], x + opts[0])
            prev = sorted(t for t in struck if o - 2 * EIGHTH <= t < o)
            run = [t for t in prev if len(_split(sorted(struck[t]))[1 - h]) >= 3]
            if len(ch) >= 3 and len(run) >= 2 and o - run[-1] <= EIGHTH and run[-1] - run[-2] <= EIGHTH:
                inotes[i].part = A.DROP
                stats["drop_inner_fast_chords"] += 1
                continue
            clean = [s_ for s_ in opts if not _pinky(*_hand_of(now + [x + s_], x + s_))]
            if clean and clean[0] != opts[0]:
                stats["inner_reordered_pinky"] += 1
            opts = clean + [s_ for s_ in opts if s_ not in clean]
        for s_ in opts:
            if com.try_commit(i, inotes, 0, s_, A.PLAIN):
                stats[f"{tier}_oct{s_:+d}"] += 1
                struck.setdefault(o, []).append(x + s_)
                break
        else:
            inotes[i].part = A.DROP
            stats[f"drop_{tier}"] += 1
    return [(n.part, n.octave, n.real) for n in inotes]


def _job(args):
    m, regimes, breath = args
    out, st = {}, Counter()
    for r in regimes:
        s = Counter()
        if r == "flute":
            out[r] = build_flute_cut(m, s) if breath == 3 else build_flute(m, s, breath)
        else:
            out[r] = (build_piano_k3(m, s) if PIANO_K3 else build_piano_k2(m, s) if breath == 3 and PIANO_K2
                      else build_piano(m, s))
        st.update({f"{r}:{k}": v for k, v in s.items()})
    return m.key, out, st


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", nargs="+", default=list(REGIMES))
    ap.add_argument("--split", default="train")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--piano-k2", action="store_true", help="K2 piano rules (R82, use --tag 3 with --breath 3)")
    ap.add_argument("--piano-k3", action="store_true", help="K3 piano rules (R83, checker-v8; use --tag 4 with --breath 3)")
    ap.add_argument("--breath", type=int, default=1, help="flute rule version: 1 (control-J/FK), 2 (R67), 3 = CUT realisation (R70, use --tag 2)")
    a = ap.parse_args(argv)
    global PIANO_K2, PIANO_K3
    PIANO_K2, PIANO_K3 = a.piano_k2, a.piano_k3
    mvs = load_split(a.split)[: a.limit]
    with Pool(a.workers) as pool:
        res = pool.map(_job, [(m, a.regimes, a.breath) for m in mvs], chunksize=1)
    tot = Counter()
    for _, _, st in res:
        tot.update(st)
    pickle.dump({k: o for k, o, _ in res}, open(RL / f"targets_fk{a.tag}__{a.split}.pkl", "wb"))
    for r in a.regimes:
        n = sum(v for k, v in tot.items() if k.startswith(r + ":") and not k.split(":")[1].startswith(("breath", "cut")))
        print(r, {k.split(":")[1]: f"{v} ({100 * v / n:.1f}%)" for k, v in sorted(tot.items()) if k.startswith(r + ":")})


if __name__ == "__main__":
    main()
