"""Readable MusicXML excerpts: the source quartet, Ou et al. unconstrained, and Ou et al.
masked, on the same bars, for performer review. Display only; nothing here feeds a result.

    python -m decoding.render_excerpts --idx 67 --start 1 --bars 16 [--masked-dir ou_band_masked]

Faithful to the source score:
  - time signature and key signature come from the original MusicXML
    (repeat-expanded exactly as headroom/sources.py does it); split bars at repeats are
    drawn as short bars under the running time signature, not as new meters;
  - onsets are exact: each beat is drawn on the coarsest grid (quarter, 8th, 16th, triplet,
    sextuplet, 32nd, 1/12) that keeps every onset in it exact, so no two notes that start
    at different times are drawn as a chord;
  - note ends are the only display change: an end within a 16th of the next onset in the
    part is drawn at that onset, otherwise at the nearest 16th or 8th-triplet point. Generated
    output often writes ends sloppily, and drawing them exactly would bury the rhythm in tuplets.
Readability: at most two voices per staff; voice-2 rests are hidden; a third overlapping
layer is drawn by shortening the held note to the new onset (counted in README.txt).

Colours (lyrics give the reason):
  red     hard violation under the current checker (letters, see LEGEND);
  orange  "3": three or more notes sounding at once in one string part, not a violation.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

from music21 import chord, clef, duration, key, meter, metadata, note, stream, tie

from arrangement.checker import check
from arrangement.checker.types import NoteArrays
from arrangement.instruments import load_ensemble

ROOT = Path(__file__).resolve().parents[1]
HEAD = ROOT / "headroom"
EX = ROOT / "decoding" / "results" / "examples"
TAG = {"range": "R", "chord_size": "C", "transition": "T", "simultaneity": "S", "hand_span": "H",
       "multistop": "M", "bow": "B", "shift": "X", "duplicate": "D", "hand_leap": "L",
       "triple_onset": "O", "triple_stretch": "W", "triple_rate": "F",
       "double_onset": "V", "restrike": "K", "double_rate": "Q", "triple_recover": "Y"}
LEGEND = {"R": "out of range", "C": "too many notes at once", "T": "leap too fast", "M": "chord does not fit the strings/hand",
          "B": "three strings held", "X": "shift too far too fast", "O": "3+ notes not struck together",
          "W": "3+-note chord too wide", "F": "3+-note chords too fast", "V": "held note under/over a new note",
          "K": "re-strikes a sounding pitch", "Q": "double stops too fast", "Y": "3+-note chord too short before the next note",
          "S": "overlap (monophonic)",
          "H": "hand span", "D": "same key twice", "L": "hand leap"}
CLEFS = {"violin": clef.TrebleClef, "viola": clef.AltoClef, "cello": clef.BassClef}
GRIDS = (1, 2, 4, 3, 6, 8, 12, 24)
from music21 import instrument as m21instrument  # noqa: E402
INSTRUMENT = {"violin": m21instrument.Violin, "viola": m21instrument.Viola, "cello": m21instrument.Violoncello,
              "flute": m21instrument.Flute, "piano": m21instrument.Piano}
TRIO_PROG = {40: 0, 41: 1, 42: 2}
PROG = {"trio": TRIO_PROG, "duo": {40: 0, 42: 1}}      # GM program -> part (Ou et al. band output)
QUARTET = ("Violin 1", "Violin 2", "Viola", "Violoncello")


# ------------------------------------------------------------------ source meta

def bar_meta(rec_key: str) -> list[dict]:
    """Per repeat-expanded bar: time signature, key (fifths), original bar number. Cached."""
    cache = EX / ".meta" / f"{rec_key[:150]}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    from arrangement.corpus import manifest
    from headroom.sources import load_raw_score, slice_movement
    row = next(r for r in manifest() if r["key"] == rec_key)
    s = slice_movement(load_raw_score(ROOT / row["file"]), row["movement"])
    if row["repeats_expanded"]:
        s = s.expandRepeats()
    out = []
    for m in s.parts[0].getElementsByClass(stream.Measure):
        ts = m.timeSignature or m.getContextByClass(meter.TimeSignature)
        ks = m.keySignature or m.getContextByClass(key.KeySignature)
        out.append({"ts": ts.ratioString if ts else None, "fifths": ks.sharps if ks else None, "number": m.number})
    first_ts = next((o["ts"] for o in out if o["ts"]), "4/4")       # a pickup bar may precede the first TS
    first_ks = next((o["fifths"] for o in out if o["fifths"] is not None), 0)
    for o in out:
        o["ts"] = o["ts"] or first_ts
        o["fifths"] = first_ks if o["fifths"] is None else o["fifths"]
        first_ts, first_ks = o["ts"], o["fifths"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


# ------------------------------------------------------------------ quantisation

def _grid_for(points: list[F], b: F) -> int:
    for g in GRIDS:
        if all((p - b) * g == round((p - b) * g) for p in points):
            if len({round((p - b) * g) for p in points}) == len(points):
                return g
    return GRIDS[-1]


def quantise(notes, t0: F, t1: F):
    """notes: (on, end, ...) with exact onsets. Onsets stay exact. Ends snap to the next onset
    in the part if it is within a 16th, else to the nearest 16th or 8th-triplet point (no
    finer), and are at least one grid step after the onset."""
    by_beat = defaultdict(set)
    for n in notes:
        by_beat[int(n[0] - t0)].add(n[0])
    grid = {b: _grid_for(sorted(ps), t0 + b) for b, ps in by_beat.items()}
    onsets = sorted({n[0] for n in notes})
    import bisect
    out = []
    for n in notes:
        on, en = n[0], min(n[1], t1)
        step = F(1, grid[int(on - t0)])
        k = bisect.bisect_right(onsets, on)
        nxt = onsets[k] if k < len(onsets) else None
        if nxt is not None and abs(nxt - en) <= F(1, 4) and nxt > on:
            e = nxt
        else:
            b = t0 + int(en - t0)
            cands = [b + F(j, g) for g in (4, 3) for j in range(g + 1)]
            e = min(cands, key=lambda c: (abs(c - en), c))
        out.append((on, min(max(e, on + step), t1)) + tuple(n[2:]))
    return out


# ------------------------------------------------------------------ score building

def _voices(chords):
    """chords: sorted [(on, end, ids)]. Two voices; a third layer cuts the held chord short."""
    voices: list[list] = [[], []]
    n_cut = 0
    for on, en, ids in chords:
        free = [v for v in voices if not v or v[-1][1] <= on]
        if free:
            free[0].append([on, en, ids])
            continue
        v = min(voices, key=lambda v: v[-1][1])
        v[-1][1] = on
        if v[-1][1] <= v[-1][0]:
            v.pop()
        v.append([on, en, ids])
        n_cut += 1
    return voices, n_cut


def _element(pitches, ql, colour_tags):
    els = [note.Note(midi=int(x)) for x in pitches]
    el = els[0] if len(els) == 1 else chord.Chord(els)
    el.duration = duration.Duration(F(ql))
    tags = set()
    for j, t in enumerate(colour_tags):
        if not t:
            continue
        tags |= t
        target = el if len(els) == 1 else el.notes[j]
        target.style.color = "#D00000" if t - {"3"} else "#E07800"
    if tags:
        el.addLyric("".join(sorted(tags, key=lambda x: (x == "3", x))))
    return el


def build(title, subtitle, part_names, inst_keys, notes, marks, bars, meta, lo, hi):
    """notes: [(on, dur, pitch, part)] (exact); marks: note index -> set of tags."""
    t0, t1 = bars[lo][0], bars[hi][0] + bars[hi][1]
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=title, movementName=subtitle)
    sc.metadata.composer = " "
    n_cut_total = 0
    for p, (pname, ik) in enumerate(zip(part_names, inst_keys)):
        raw = [(on, on + du, x, i) for i, (on, du, x, q) in enumerate(notes) if q == p and t0 <= on < t1]
        qn = quantise(raw, t0, t1)
        groups = defaultdict(list)
        for on, en, x, i in qn:
            groups[(on, en)].append(i)
        chords = sorted(((on, en, sorted(ids, key=lambda i: notes[i][2])) for (on, en), ids in groups.items()),
                        key=lambda c: (c[0], -notes[c[2][-1]][2]))
        voices, n_cut = _voices(chords)
        n_cut_total += n_cut
        part = stream.Part(id=f"P{p}")
        part.partName = pname
        inst = INSTRUMENT.get(ik, m21instrument.Instrument)()   # so MuseScore plays a string sound, not piano
        inst.partName = pname
        part.insert(0, inst)
        prev_ts = prev_k = None
        for k in range(lo, hi + 1):
            start, length = bars[k]
            md = meta[k] if k < len(meta) else meta[-1]
            m = stream.Measure(number=k + 1)      # repeat-expanded bar number (original number in README)
            if k == lo:
                m.insert(0, CLEFS.get(ik, clef.TrebleClef)())
            if md["fifths"] != prev_k:
                m.insert(0, key.KeySignature(md["fifths"])); prev_k = md["fifths"]
            if md["ts"] != prev_ts:
                m.insert(0, meter.TimeSignature(md["ts"])); prev_ts = md["ts"]
            if F(meter.TimeSignature(md["ts"]).barDuration.quarterLength).limit_denominator(1000) != length:
                m.duration = duration.Duration(F(length))       # split bar (repeat) or pickup
            for vi, v in enumerate(voices):
                segs = [(max(on, start), min(en, start + length), ids, on < start, en > start + length)
                        for on, en, ids in v if on < start + length and en > start]
                if vi == 1 and not segs:
                    continue
                vo = stream.Voice(id=str(vi + 1))
                t = start
                for a, b, ids, cont_in, cont_out in segs:
                    if a > t:
                        r = note.Rest(quarterLength=F(a - t))
                        if vi == 1:
                            r.style.hideObjectOnPrint = True
                        vo.insert(float(t - start), r)
                    el = _element([notes[i][2] for i in ids], b - a,
                                  [marks.get(i, set()) if not cont_in else set() for i in ids])
                    if cont_in or cont_out:
                        el.tie = tie.Tie("continue" if cont_in and cont_out else "stop" if cont_in else "start")
                    vo.insert(float(a - start), el)
                    t = b
                if t < start + length:
                    r = note.Rest(quarterLength=F(start + length - t))
                    if vi == 1:
                        r.style.hideObjectOnPrint = True
                    vo.insert(float(t - start), r)
                m.insert(0, vo)
            part.append(m)
        sc.insert(0, part)
    sc.makeNotation(inPlace=True)
    return sc, n_cut_total


# ------------------------------------------------------------------ data

def load_source(rec):
    return [(F(o), F(d), int(x), int(p)) for p, o, d, x in rec["notes"]]


def load_ou(path, prog=TRIO_PROG):
    g = json.loads(Path(path).read_text())
    return [(F(o), F(d), int(x), prog[int(p)]) for p, o, d, x in g["notes"] if int(p) in prog]


def hard_marks(notes, ens) -> dict[int, set]:
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    marks: dict[int, set] = defaultdict(set)
    import numpy as np
    for v in check(na, ens, np.array([n[3] for n in notes])):
        ids = v.note_ids
        if v.check in ("transition", "shift"):
            ids = ids[1:]
        elif v.check in ("double_onset", "triple_onset", "restrike", "double_rate", "triple_rate", "bow", "triple_recover"):
            # the notes that arrive last caused it
            t = max(notes[i][0] for i in ids)
            ids = [i for i in ids if notes[i][0] == t]
        for i in ids:
            marks[i].add(TAG[v.check])
    return marks


def multistops(notes, ens) -> dict[int, set]:
    out = defaultdict(set)
    by_part = defaultdict(list)
    for i, n in enumerate(notes):
        by_part[n[3]].append(i)
    for p, ids in by_part.items():
        if ens.instruments[p].strings is None:
            continue
        for i in ids:
            on = notes[i][0]
            S = [j for j in ids if notes[j][0] <= on < notes[j][0] + notes[j][1]]
            if len({notes[j][2] for j in S}) >= 3:
                for j in S:
                    out[j].add("3")
    return out


def load_record(path, key):
    for line in open(path):
        r = json.loads(line)
        if r["input_id"] == key:
            return [(F(o), F(d), int(x), int(p)) for p, o, d, x in r["output"]["notes"]]
    raise KeyError(key)


def merge_unisons(notes, marks):
    """Display only: notes of one part with the same onset and pitch are drawn as one note (the longest),
    carrying the union of their marks. Returns (notes, marks, number merged). The data is unchanged
    (checker marks are computed before merging)."""
    best: dict = {}
    for i, (o, d, x, p) in enumerate(notes):
        k = (p, o, x)
        if k not in best or d > notes[best[k]][1]:
            best[k] = i
    keep = sorted(best.values())
    groups = defaultdict(set)
    for i, (o, d, x, p) in enumerate(notes):
        groups[best[(p, o, x)]] |= marks.get(i, set())
    new_marks = defaultdict(set)
    for j, i in enumerate(keep):
        if groups[i]:
            new_marks[j] = groups[i]
    return [notes[i] for i in keep], new_marks, len(notes) - len(keep)


def render(idx: int, start_bar: int, n_bars: int, masked_dir: str, out_root: Path = EX,
           model_run: str | None = None, regime: str = "trio", extra: list | None = None) -> Path:
    """extra: [(file stem, label, records path)] rendered after the others (e.g. the oracle under mask)."""
    rec = json.loads((HEAD / "data" / "sources" / f"{idx:03d}.json").read_text())
    bars = [(F(a), F(b)) for a, b in rec["bars"]]
    meta = bar_meta(rec["key"])
    lo = start_bar - 1
    hi = min(lo + n_bars, len(bars)) - 1
    t0, t1 = bars[lo][0], bars[hi][0] + bars[hi][1]
    comp, work = rec["key"].split("__")[0].replace("_", " "), rec["key"].split("__")[1].replace("_", " ")
    mv = rec["key"].rsplit("__m", 1)[1]
    nums = f"{lo + 1}-{hi + 1}"
    orig = ", ".join(f"{k + 1}={meta[k]['number']}" for k in range(lo, min(hi + 1, len(meta))))
    out = out_root / f"{idx:03d}_bars{nums}"
    out.mkdir(parents=True, exist_ok=True)
    trio, quartet = load_ensemble(regime), load_ensemble("quartet")
    lines = []
    files = [("0_source_quartet", "Source string quartet", load_source(rec), quartet, QUARTET)]
    for fname, label, d in ((f"1_ou_unconstrained_{regime}", f"Ou et al. {regime}, unconstrained", "ou_band"),
                            (f"2_ou_masked_{regime}", f"Ou et al. {regime}, masked ({masked_dir})", masked_dir)):
        files.append((fname, label, load_ou(HEAD / "data" / "out" / d / regime / f"{idx:03d}.json", PROG[regime]), trio,
                      trio.part_names))
    if model_run:   # the trained arranger (MODEL.md), from its arrangement records
        rd = ROOT / "model" / "results" / model_run / "records"
        for fname, label, sy in ((f"3_arranger_{regime}", f"Arranger ({model_run}) {regime}, unmasked", "arranger"),
                                 (f"4_arranger_masked_{regime}", f"Arranger ({model_run}) {regime}, masked", "arranger_masked")):
            files.append((fname, label, load_record(rd / f"{sy}__{regime}.jsonl", rec["key"]), trio, trio.part_names))
    for fname, label, path in extra or []:
        files.append((fname, label, load_record(path, rec["key"]), trio, trio.part_names))
    for fname, label, notes, ens, names in files:
        marks = hard_marks(notes, ens)
        for i, s in multistops(notes, ens).items():
            marks[i] |= s
        notes, marks, n_uni = merge_unisons(notes, marks)
        sc, n_cut = build(label, f"{comp}, {work}, mvt {int(mv)}, bars {nums}", names,
                          [i.key for i in ens.instruments], notes, marks, bars, meta, lo, hi)
        sc.write("musicxml", fp=str(out / f"{fname}.musicxml"))
        win = [i for i, n in enumerate(notes) if t0 <= n[0] < t1]
        red = sum(1 for i in win if marks.get(i, set()) - {"3"})
        orange = sum(1 for i in win if marks.get(i) == {"3"})
        lines.append(f"{label}: {len(win)} notes; {red} red (hard violation); {orange} orange only"
                     + (f"; {n_cut} held notes shortened for display (3rd voice)" if n_cut else "")
                     + (f"; {n_uni} unison duplicates drawn as one note" if n_uni else ""))
    legend = "\n".join(f"  {k}  {v}" for k, v in LEGEND.items())
    (out / "README.txt").write_text(f"{rec['key']}\n\nBars are numbered along the repeat-expanded timeline "
                                    f"(the numbering used in review so far). Original score bar numbers: {orig}\n"
                                    f"{__doc__}\nLEGEND\n{legend}\n\n" + "\n".join(lines) + "\n")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, nargs="+", default=[67])
    ap.add_argument("--start", type=int, nargs="+", default=[1])
    ap.add_argument("--bars", type=int, default=16)
    ap.add_argument("--masked-dir", default="ou_band_masked")
    ap.add_argument("--out", default=str(EX))
    ap.add_argument("--model-run", default=None, help="also render the trained arranger's records")
    ap.add_argument("--regime", default="trio", choices=["trio", "duo"])
    ap.add_argument("--oracle", action="store_true", help="also render the oracle under the mask (BLOCK4.md 1a)")
    a = ap.parse_args(argv)
    starts = a.start * len(a.idx) if len(a.start) == 1 else a.start
    for i, s in zip(a.idx, starts):
        extra = ([(f"5_oracle_under_mask_{a.regime}", f"Oracle (true reduction) under the checker-v4 mask, {a.regime}",
                   ROOT / "model" / "results" / "diagnostics" / "records" / f"oracle_mask_model__{a.regime}.jsonl")]
                 if a.oracle else None)
        o = render(i, s, a.bars, a.masked_dir, Path(a.out), a.model_run, a.regime, extra)
        print(o); print((o / "README.txt").read_text().rsplit("\n\n", 1)[-1])


if __name__ == "__main__":
    main()
