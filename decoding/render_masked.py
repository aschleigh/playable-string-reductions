"""MuseScore files: Ou et al. trio, unconstrained vs gate-masked, on one excerpt.

    python -m decoding.render_masked --idx 67 --bars 1-16

Red = hard-tier violation (current checker, checker-v3, for every file; computed on the whole movement); lyric R/C/T (v1), M multistop, B bow, X shift (v2), O not struck together, W 3+-note stretch, F chords too fast (v3).
Orange, lyric "3" = three or more distinct pitches sounding at once in one string part.
That is NOT by itself a hard-tier rule; it marks where three strings sound at once.
Blue, lyric "~" = display rounding: onsets are drawn on a 16th grid, so notes that start at
different times in the data (e.g. 32nds) can be drawn as one chord. They are not a chord.
Display only; nothing here feeds a result.
"""
from __future__ import annotations

import argparse
import json
from fractions import Fraction

from arrangement.instruments import load_ensemble
from headroom.render_examples import HEAD, build_score, display_notes, flagged, snap

TRIO_PROG = {40: 0, 41: 1, 42: 2}


def multistops(notes, assign) -> dict[int, set]:
    """Notes in a moment where >= 3 distinct pitches sound in the same part."""
    marks = {}
    for i, (o, d, x) in enumerate(notes):
        same = [j for j, (o2, d2, x2) in enumerate(notes)
                if assign[j] == assign[i] and o2 <= o < o2 + d2]
        if len({notes[j][2] for j in same}) >= 3:
            for j in same:
                marks.setdefault(j, set()).add("3")
    return marks


def rounded(notes, assign) -> dict[int, set]:
    """Notes drawn at the same 16th as a note that starts at a different time in the data.
    The display rounds onsets to 16ths, so these look like a chord but are not one."""
    groups = {}
    for i, (o, d, x) in enumerate(notes):
        groups.setdefault((assign[i], snap(o)), []).append(i)
    return {i: {"~"} for ids in groups.values() if len({notes[i][0] for i in ids}) > 1 for i in ids}


def load_ou(path):
    g = json.loads(path.read_text())
    n = sorted(((Fraction(o), Fraction(d), int(x), TRIO_PROG[int(p)]) for p, o, d, x in g["notes"]
                if int(p) in TRIO_PROG), key=lambda n: (n[0], n[2], n[1], n[3]))
    return [x[:3] for x in n], [x[3] for x in n]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, default=67)
    ap.add_argument("--bars", default="1-16")
    a = ap.parse_args(argv)
    lo, hi = (int(x) - 1 for x in a.bars.split("-"))
    rec = json.loads((HEAD / "data" / "sources" / f"{a.idx:03d}.json").read_text())
    bars = [(Fraction(s), Fraction(l)) for s, l in rec["bars"]]
    trio = load_ensemble("trio")
    out = HEAD.parent / "decoding" / "results" / "examples" / f"{a.idx:03d}_bars{a.bars}_checker-v3"
    out.mkdir(parents=True, exist_ok=True)
    t0, t1 = bars[lo][0], bars[hi][0] + bars[hi][1]
    lines = []
    piece = f"{rec['key'].split('__')[0].split(',')[0]} (eval movement {a.idx}), bars {a.bars}"
    for fname, label, sysdir in [("1_ou_unconstrained_trio", "Ou et al. trio, unconstrained", "ou_band"),
                                 ("2_ou_masked_checker-v2_trio", "Ou et al. trio, masked by checker-v2",
                                  "ou_band_masked_checker-v2"),
                                 ("3_ou_masked_checker-v3_trio", "Ou et al. trio, masked by checker-v3", "ou_band_masked")]:
        notes, assign = load_ou(HEAD / "data" / "out" / sysdir / "trio" / f"{a.idx:03d}.json")
        hard = flagged(notes, trio, assign)
        marks = {i: set(s) for i, s in hard.items()}
        for i, s in multistops(notes, assign).items():
            marks.setdefault(i, set()).update(s)
        for i, s in rounded(notes, assign).items():
            marks.setdefault(i, set()).update(s)
        sc, n_red, n_cut = build_score(f"{label}: {piece}", trio, display_notes(notes), assign, marks, bars, lo, hi)
        sc.write("musicxml", fp=str(out / f"{fname}.musicxml"))
        win = [i for i, n in enumerate(notes) if t0 <= n[0] < t1]
        n_hard = sum(1 for i in win if hard.get(i))
        n_round = sum(1 for i in win if "~" in marks.get(i, set()))
        n_multi = sum(1 for i in win if "3" in marks.get(i, set()) and not hard.get(i))
        lines.append(f"{label}: {len(win)} notes in excerpt; {n_hard} red (hard violation); "
                     f"{n_multi} orange only (>= 3-note sounding chord, not a hard rule)"
                     + f"; {n_round} blue (drawn merged by 16th rounding, not simultaneous)"
                     + (f"; {n_cut} held notes shortened for display (>4 voices)" if n_cut else ""))
    (out / "README.txt").write_text(f"{rec['key']}\n\n{__doc__}\n" + "\n".join(lines) + "\n")
    print(out); print("\n".join(lines))


if __name__ == "__main__":
    main()
