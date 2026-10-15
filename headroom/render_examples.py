"""Side-by-side MusicXML examples with unplayable notes in red (open in MuseScore).

    python -m headroom.render_examples --idx 67 --bars 1-16

For one evaluation movement, writes headroom/results/examples/<idx>_<bars>/:
  0_original_quartet.musicxml   the source (true parts)
  1_naive_trio.musicxml         rule-based, pitch bands only
  2_continuity_trio.musicxml    rule-based, line-keeping
  3_ou_et_al_trio.musicxml      neural (Ou et al., released weights)
Violations are computed on the WHOLE movement with the frozen checker, exactly
as in the measurement; only the excerpt is drawn. Each violating note is red
and carries a lyric: R = range, C = chord size, T = transition (marked on the
second note of the leap). Display only: nothing here feeds the results.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
from music21 import chord, clef, duration, layout, metadata, meter, note, stream

from arrangement.assign import continuity, naive
from arrangement.checker import check
from arrangement.checker.types import NoteArrays
from arrangement.instruments import load_ensemble

HEAD = Path(__file__).resolve().parent
TAG = {"range": "R", "chord_size": "C", "transition": "T", "simultaneity": "S", "hand_span": "H",
       "multistop": "M", "bow": "B", "shift": "X", "duplicate": "D", "hand_leap": "L",   # checker-v2
       "triple_onset": "O", "triple_stretch": "W", "triple_rate": "F"}   # checker-v3
CLEFS = {"violin": clef.TrebleClef, "viola": clef.AltoClef, "cello": clef.BassClef}
TRIO_PROG = {40: 0, 41: 1, 42: 2}


def _ts(length: Fraction):
    for den in (4, 8, 16, 2):
        num = length * den / 4
        if num.denominator == 1 and num.numerator >= 1:
            return f"{num.numerator}/{den}"
    return "4/4"


def flagged(notes, ens, assign) -> dict[int, set[str]]:
    arr = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    marks: dict[int, set[str]] = defaultdict(set)
    for v in check(arr, ens, np.asarray(assign, dtype=np.int64)):
        ids = v.note_ids[-1:] if v.check == "transition" else v.note_ids
        for i in ids:
            marks[i].add(TAG[v.check])
    return marks


def snap(x: Fraction) -> Fraction:
    """Nearest 16th (1/4 quarter). Mixing 16th and triplet grids leaves 1/12 gaps that MuseScore rejects."""
    return Fraction(round(x * 4), 4)


def display_notes(notes):
    out = []
    for on, du, pi in notes:
        o, e = snap(on), snap(on + du)
        out.append((o, max(e - o, Fraction(1, 4)), pi))
    return out


def build_score(title, ens, notes, assign, marks, bars, lo, hi) -> tuple[stream.Score, int]:
    t0, t1 = bars[lo][0], bars[hi][0] + bars[hi][1]
    sc = stream.Score()
    label, _, sub = title.partition(": ")
    sc.metadata = metadata.Metadata(title=label, movementName=sub)
    sc.metadata.composer = " "
    n_red = 0
    n_cut = [0]
    for p, inst in enumerate(ens.instruments):
        part = stream.Part(id=f"P{p}")
        part.partName = ens.part_names[p]
        groups = defaultdict(list)                    # (onset, dur) -> note ids  => chords
        for i, (on, du, pi) in enumerate(notes):
            if assign[i] == p and t0 <= on < t1:
                groups[(on, min(du, t1 - on))].append(i)
        voices: list[list] = []                       # greedy voice packing for overlaps, max 4 (MuseScore)
        for (on, du), ids in sorted(groups.items()):
            for v in voices:
                if v[-1][0] + v[-1][1] <= on:
                    v.append((on, du, ids)); break
            else:
                if len(voices) < 4:
                    voices.append([(on, du, ids)])
                else:                                 # display only: cut the earliest-ending held note short
                    v = min(voices, key=lambda v: (v[-1][0] + v[-1][1], voices.index(v)))
                    po, pd, pids = v[-1]
                    if po == on:                      # same onset: show as one chord at the shorter length
                        v[-1] = (po, min(pd, du), pids + ids)
                    else:
                        v[-1] = (po, on - po, pids)
                        v.append((on, du, ids))
                    n_cut[0] += 1
        measures = []
        prev_ts = None
        for k in range(lo, hi + 1):
            start, length = bars[k]
            m = stream.Measure(number=k + 1)
            if k == lo:
                m.insert(0, CLEFS[inst.key]())
            ts = _ts(length)
            if ts != prev_ts:
                m.insert(0, meter.TimeSignature(ts)); prev_ts = ts
            for vi, v in enumerate(voices or [[]]):
                vo = stream.Voice(id=str(vi + 1))
                for on, du, ids in v:
                    if not (start <= on < start + length):
                        continue
                    d = min(du, start + length - on)        # clip at barline (display only)
                    els = [note.Note(midi=int(notes[i][2])) for i in ids]
                    el = els[0] if len(els) == 1 else chord.Chord(els)
                    el.duration = duration.Duration(float(d))
                    tags = set()
                    for j, i in enumerate(ids):
                        if marks.get(i):
                            tags |= marks[i]
                            n_red += 1
                            (el if len(ids) == 1 else el.notes[j]).style.color = (
                                "#E00000" if marks[i] - {"3", "~"} else "#E07800" if "3" in marks[i] else "#1060E0")
                    if tags:
                        el.addLyric("".join(sorted(tags)))
                    vo.insert(float(on - start), el)
                if not len(vo) and vi == 0:
                    vo.insert(0, note.Rest(quarterLength=float(length)))
                elif len(vo):
                    filled = stream.Voice(id=vo.id)
                    t = Fraction(0)
                    for el in sorted(vo.notes, key=lambda e: e.offset):
                        off = Fraction(el.offset).limit_denominator(1000)
                        if off > t:
                            filled.insert(float(t), note.Rest(quarterLength=float(off - t)))
                        filled.insert(float(off), el)
                        t = off + Fraction(el.quarterLength).limit_denominator(1000)
                    if t < length:
                        filled.insert(float(t), note.Rest(quarterLength=float(length - t)))
                    vo = filled
                if len(vo):
                    m.insert(0, vo)
            measures.append(m)
        for m in measures:
            part.append(m)
        sc.insert(0, part)
    sc.insert(0, layout.StaffGroup(list(sc.parts), symbol="bracket"))
    return sc, n_red, n_cut[0]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, default=67)
    ap.add_argument("--bars", default="1-16")
    a = ap.parse_args(argv)
    lo, hi = (int(x) - 1 for x in a.bars.split("-"))
    rec = json.loads((HEAD / "data" / "sources" / f"{a.idx:03d}.json").read_text())
    bars = [(Fraction(s), Fraction(l)) for s, l in rec["bars"]]
    src = sorted(((Fraction(o), Fraction(d), int(x), int(p)) for p, o, d, x in rec["notes"]),
                 key=lambda n: (n[0], n[2], n[1], n[3]))
    plain = [n[:3] for n in src]
    quartet, trio = load_ensemble("quartet"), load_ensemble("trio")
    arr = NoteArrays.from_notes([n[0] for n in plain], [n[1] for n in plain], [n[2] for n in plain])
    ou = json.loads((HEAD / "data" / "out" / "ou_band" / "trio" / f"{a.idx:03d}.json").read_text())
    ou_notes = sorted(((Fraction(o), Fraction(d), int(x), TRIO_PROG[int(g)]) for g, o, d, x in ou["notes"]
                       if int(g) in TRIO_PROG), key=lambda n: (n[0], n[2], n[1], n[3]))
    versions = [
        ("0_original_quartet", "Original quartet (composer)", quartet, plain, [n[3] for n in src]),
        ("1_naive_trio", "Naive rule-based trio", trio, plain, naive(arr, trio)),
        ("2_continuity_trio", "Continuity rule-based trio", trio, plain, continuity(arr, trio)),
        ("3_ou_et_al_trio", "Ou et al. (neural) trio", trio, [n[:3] for n in ou_notes], [n[3] for n in ou_notes]),
    ]
    piece = f"{rec['key'].split('__')[0].split(',')[0]} (eval movement {a.idx})"
    out = HEAD / "results" / "examples" / f"{a.idx:03d}_bars{a.bars}"
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for fname, label, ens, notes, assign in versions:
        marks = flagged(notes, ens, assign)                   # always on the exact notes
        shown = display_notes(notes) if fname.startswith("3_") else notes
        sc, n_red, n_cut = build_score(f"{label}: {piece}, bars {a.bars}", ens, shown, list(assign), marks, bars, lo, hi)
        sc.write("musicxml", fp=str(out / f"{fname}.musicxml"))
        n_win = sum(1 for n in notes if bars[lo][0] <= n[0] < bars[hi][0] + bars[hi][1])
        summary.append(f"{label}: {n_win} notes in excerpt, {n_red} red"
                       + (f", {n_cut} held notes shortened for display (>4 voices)" if n_cut else ""))
    (out / "README.txt").write_text(
        f"{rec['key']} (eval idx {a.idx}), bars {a.bars}\n"
        "Red = violates the frozen checker (computed on the whole movement). Lyric: R range, C chord size,\n"
        "T transition (on the second note of the leap). Notes are clipped at barlines for display.\n"
        "Ou et al. rhythms are snapped to the nearest 16th for display only (its raw output\n"
        "uses a 1/12-beat grid that MuseScore cannot import); red flags come from the exact output.\n\n"
        + "\n".join(summary) + "\n")
    print(out); print("\n".join(summary))


if __name__ == "__main__":
    main()
