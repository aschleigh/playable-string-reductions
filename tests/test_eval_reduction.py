"""METRICS 1.4.0-draft reduction metrics (arrangement/eval/reduction.py)."""
from fractions import Fraction as F

from arrangement.eval.record import Score
from arrangement.eval.reduction import double_stops, retention, voice_tiers

SRC_PARTS = (("Violin 1", "violin"), ("Violin 2", "violin"), ("Viola", "viola"), ("Violoncello", "cello"))
TRIO = (("Violin", "violin"), ("Viola", "viola"), ("Violoncello", "cello"))


def n(p, o, d, x):
    return (p, F(o), F(d), x)


def test_tiers_top_inner_bass_and_alone():
    notes = [n(0, 0, 1, 76), n(1, 0, 1, 72), n(2, 0, 1, 64), n(3, 0, 1, 48), n(0, 2, 1, 70)]
    assert voice_tiers(notes) == ["top", "inner", "inner", "bass", "top"]


def test_tiers_follow_sounding_pitch_and_held_notes():
    # Vn2 crosses above Vn1; a note starting under a held higher note is not top
    notes = [n(0, 0, 1, 70), n(1, 0, 1, 74), n(3, 0, 4, 50), n(0, 1, 1, 60)]
    assert voice_tiers(notes) == ["inner", "top", "bass", "top"]
    held = [n(0, 0, 4, 80), n(1, 1, 1, 70), n(3, 1, 1, 50)]
    assert voice_tiers(held) == ["top", "inner", "bass"]


def test_unison_ties_upward():
    assert voice_tiers([n(0, 0, 1, 72), n(1, 0, 1, 72), n(3, 0, 1, 48)]) == ["top", "top", "bass"]


def test_retention_tolerance_and_any_part():
    src = Score(SRC_PARTS, (n(0, 0, 1, 76), n(2, 0, 1, 64), n(3, 0, 1, 48)))
    out = Score(TRIO, (n(2, F(1, 8), 1, 76), n(1, F(1, 4), 1, 64)))   # top kept (any part); inner off by a 16th
    r = retention(out, src)
    assert r["retention__top"] == 1.0 and r["retention__inner"] == 0.0 and r["retention__bass"] == 0.0
    assert r["weighted_fidelity__C"] == 1 / 3
    assert abs(r["weighted_fidelity__A"] - 1.0 / (1.0 + 0.25 + 0.8)) < 1e-12


def test_double_stops_supported_vs_merged():
    src = Score(SRC_PARTS, (n(1, 0, 2, 67), n(1, 0, 2, 74), n(0, 0, 1, 79), n(0, 1, 1, 81)))
    # violin holds the source Vn2 double stop (supported), then adds Vn1's line on top (merged)
    out = Score(TRIO, (n(0, 0, 2, 67), n(0, 0, 2, 74), n(0, 1, 1, 81)))
    d = double_stops(out, src)
    assert d["double_stop_events"] == 2 and d["unneeded_double_stops"] == 1
    assert d["unneeded_double_stops__by_part"] == [1, 0, 0]
