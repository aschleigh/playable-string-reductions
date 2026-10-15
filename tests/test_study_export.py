"""The performer sees exactly the notes the checker judged: an exported excerpt,
read back from MusicXML, has the same (onset, duration, pitch) multiset."""
from __future__ import annotations

from fractions import Fraction as F

import pytest
from study.select_excerpts import build
from study.verify_packets import read_notes


def _roundtrip(c, tmp_path):
    p = tmp_path / "x.musicxml"
    build(c, "Excerpt T01").write("musicxml", fp=str(p))
    return read_notes(p)


def _c(instrument, notes, lengths=("4", "4", "4", "4")):
    return {"instrument": instrument, "bar_lengths": list(lengths),
            "notes": [[str(F(o)), str(F(d)), x] for o, d, x in notes]}


@pytest.mark.parametrize("instrument,notes", [
    ("violin", [(0, 1, 67), (1, F(1, 2), 69), (F(3, 2), F(1, 2), 71), (2, 2, 72), (4, 6, 74), (10, 6, 76)]),
    ("cello", [(0, 4, 36), (0, 4, 43), (4, F(1, 3), 50), (F(13, 3), F(1, 3), 52), (F(14, 3), F(1, 3), 53),
               (5, 3, 55), (8, 8, 48)]),
    ("flute", [(0, 2, 72), (1, 2, 76), (3, 1, 79), (4, 12, 84)]),   # overlapping: needs a second voice
])
def test_export_roundtrip(instrument, notes, tmp_path):
    assert _roundtrip(_c(instrument, notes), tmp_path) == sorted((F(o), F(d), x) for o, d, x in notes)


def test_piano_splits_staves_but_keeps_notes(tmp_path):
    notes = [(0, 2, 48), (0, 2, 64), (0, 2, 67), (2, 2, 43), (2, 2, 72), (4, 4, 60), (8, 8, 36)]
    assert _roundtrip(_c("piano", notes), tmp_path) == sorted((F(o), F(d), x) for o, d, x in notes)


def test_three_four_bars(tmp_path):
    notes = [(0, 3, 67), (3, 1, 69), (4, 2, 71), (6, 6, 72)]
    assert _roundtrip(_c("viola", notes, ("3", "3", "3", "3")), tmp_path) == sorted((F(o), F(d), x) for o, d, x in notes)
