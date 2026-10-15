"""Step 3: rule-based assigners."""
import ast
from pathlib import Path

import numpy as np

from arrangement.assign import ContinuityParams, bands, continuity, naive
from arrangement.instruments import load_ensemble
from checker_helpers import build

QUARTET = load_ensemble("quartet")


def test_quartet_bands_partition_pitch_line():
    b = bands(QUARTET)
    assert b[0][1] == np.inf and b[3][0] == -np.inf
    assert b[0][0] == b[1][1] and b[1][0] == b[2][1] and b[2][0] == b[3][1]   # contiguous, V1 > V2 > Va > Vc
    vn, va, vc = (QUARTET.instruments[i] for i in (0, 2, 3))
    c_vn, c_va, c_vc = ((i.low + i.high) / 2 for i in (vn, va, vc))
    assert b[1][0] == (c_vn + c_va) / 2 and b[2][0] == (c_va + c_vc) / 2      # midpoints of range centres
    assert b[0][0] == (b[1][0] + vn.high) / 2                                 # violins split their span evenly


def test_naive_uses_pitch_only():
    notes, _ = build([(0, 1, 90, 0), (0, 1, 80, 0), (0, 1, 70, 0), (0, 1, 50, 0), (5, 1, 90, 0), (5, 1, 30, 0)])
    assert naive(notes, QUARTET).tolist() == [0, 1, 2, 3, 0, 3]


def test_continuity_keeps_lines_through_band_boundary():
    # Upper line descends across the V2/Va boundary (74.5) while the viola
    # holds a lower line: continuity keeps the upper line in one part.
    upper = [(k, 1, 78 - 2 * k, -1) for k in range(5)]          # 78 76 74 72 70
    lower = [(k, 1, 65, -1) for k in range(5)]
    notes, _ = build(upper + lower)
    a = continuity(notes, QUARTET)
    assert len(set(a[:5].tolist())) == 1
    assert len(set(a[5:].tolist())) == 1 and a[0] != a[5]
    assert len(set(naive(notes, QUARTET)[:5].tolist())) == 2      # naive splits the line


def test_continuity_spreads_chords_but_allows_double_stops():
    notes, _ = build([(0, 1, x, -1) for x in (90, 88, 86, 84)])
    a = continuity(notes, QUARTET, ContinuityParams(1.0, 1.0, 100.0))
    assert len(set(a.tolist())) == 4
    six, _ = build([(0, 1, x, -1) for x in (40, 50, 60, 70, 80, 90)])
    assert len(continuity(six, QUARTET)) == 6                       # >P notes still all assigned


def test_grace_note_follows_nearest_real_note():
    notes, _ = build([(0, 1, 48, -1), (1, 0, 91, -1, True), (1, 1, 90, -1), (1, 1, 50, -1)])
    a = continuity(notes, QUARTET)
    assert a[1] == a[2]


def test_assigners_are_deterministic_and_complete():
    rng = np.random.default_rng(3)
    rows = [(float(o), 0.5, int(p), -1) for o, p in zip(np.sort(rng.integers(0, 40, 300)) / 2, rng.integers(36, 96, 300))]
    notes, _ = build(rows)
    for fn in (naive, continuity):
        a, b = fn(notes, QUARTET), fn(notes, QUARTET)
        assert (a == b).all() and ((a >= 0) & (a < 4)).all()


def test_assigner_never_imports_checker():
    tree = ast.parse((Path(__file__).resolve().parent.parent / "arrangement" / "assign.py").read_text())
    mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    # NoteArrays is a plain data type; nothing from the checker's logic.
    assert all(not m.startswith("arrangement.checker") or m == "arrangement.checker.types" for m in mods)


def test_forbid_mode_never_crosses_within_a_slice():
    rng = np.random.default_rng(5)
    rows = [(float(o), 1.0, int(p), -1) for o, p in zip(np.sort(rng.integers(0, 30, 400)), rng.integers(36, 96, 400))]
    notes, _ = build(rows)
    a = continuity(notes, QUARTET)            # config default: crossing forbid
    rank = {0: 0, 1: 1, 2: 2, 3: 3}           # band order V1 > V2 > Va > Vc
    for t in np.unique(notes.onset):
        sl = np.flatnonzero(notes.onset == t)
        by_pitch = sl[np.argsort(-notes.pitch[sl], kind="stable")]
        ranks = [rank[int(a[i])] for i in by_pitch]
        assert ranks == sorted(ranks)


def test_allow_mode_and_bad_mode():
    notes, _ = build([(0, 1, x, -1) for x in (90, 70, 60, 45)])
    a = continuity(notes, QUARTET, ContinuityParams(1.0, 0.0, 64.0, "allow"))
    assert sorted(a.tolist()) == [0, 1, 2, 3]
    import pytest
    with pytest.raises(ValueError):
        continuity(notes, QUARTET, ContinuityParams(1.0, 0.0, 64.0, "sideways"))
