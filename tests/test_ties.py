"""Tie merging: a tied group is ONE event with summed duration, including ties
on only some pitches of a chord and ties from a single note into a chord.

The legacy path (parsing.load_score -> stripTies -> extract_note_events)
splits those cases; test_legacy_parser_splits_chord_ties pins that bug."""
import glob
from fractions import Fraction

import pytest
from music21 import pitch

import parsing
from arrangement.parse import collect_pitch_instances, load_raw_score, tie_merged_groups
from conftest import ROOT

FIXTURE = ROOT / "tests" / "fixtures" / "ties.musicxml"
F = Fraction


def _name(midi):
    return pitch.Pitch(midi=midi).nameWithOctave


def _summ(groups, stream_idx):
    return [(_name(g.first.midi), g.onset, g.duration) for g in groups if g.first.stream_idx == stream_idx]


# Hand-derived from tests/fixtures/make_ties_fixture.py (2/4, quarter = 1.0).
EXPECTED_P1 = [
    ("C4", 0, 3), ("E4", 0, 3),                               # m1-2 whole chord tied
    ("C4", 4, 3), ("E4", 4, 2), ("E4", 6, 1), ("G4", 6, 1),   # m3-4 only C4 tied
    ("D4", 8, 3), ("A4", 10, 1),                              # m5-6 note tied into chord
    ("F4", 12, 5), ("A4", 12, 2),                             # m7-9 chain start/continue/stop
    ("B4", 18, 0), ("C5", 18, 2),                             # m10 grace + note
    ("E4", 20, 1), ("E4", 21, 1),                             # m11 re-struck, not tied
]
EXPECTED_P2 = [("G4", 0, 3), ("C4", 0, 2), ("E5", 2, 2)]      # tie from voice 1 into voice 2


@pytest.fixture(scope="module")
def fixture_result():
    return tie_merged_groups(load_raw_score(FIXTURE).toSoundingPitch())


def test_fixture_raw_instance_count():
    assert len(collect_pitch_instances(load_raw_score(FIXTURE))) == 20 + 4  # P1: 2+2+2+3+1+2+2+1+1+2+2; P2: G4 C4 E5 G4


def test_fixture_merged_events(fixture_result):
    groups, _ = fixture_result
    assert _summ(groups, 0) == [(n, F(o), F(d)) for n, o, d in EXPECTED_P1]
    assert _summ(groups, 1) == [(n, F(o), F(d)) for n, o, d in EXPECTED_P2]


def test_fixture_grace_flagged_zero_duration(fixture_result):
    groups, _ = fixture_result
    graces = [g for g in groups if g.first.is_grace]
    assert [(_name(g.first.midi), g.duration) for g in graces] == [("B4", 0)]


def test_fixture_cross_voice_tie_logged(fixture_result):
    _, anomalies = fixture_result
    assert [(a.kind, a.stream_idx, _name(a.midi)) for a in anomalies] == [("cross_voice", 1, "G4")]


def test_fixture_group_ids_stable(fixture_result):
    groups, _ = fixture_result
    again, _ = tie_merged_groups(load_raw_score(FIXTURE).toSoundingPitch())
    assert [(g.group_id, g.onset, g.first.midi) for g in groups] == \
           [(g.group_id, g.onset, g.first.midi) for g in again]
    assert [g.group_id for g in groups] == list(range(len(groups)))


@pytest.mark.xfail(strict=True, reason="legacy stripTies splits partial-chord and note->chord ties")
def test_legacy_parser_splits_chord_ties():
    score = parsing.load_score(FIXTURE, {"parsing": {"part_granularity": "staff"}})
    ev = parsing.extract_note_events(score).notes
    got = sorted((_name(e.pitch_midi), e.onset, e.duration) for e in ev if e.part_index == 0)
    assert got == sorted((n, float(o), float(d)) for n, o, d in EXPECTED_P1)


def test_real_partial_chord_tie_op132_violin2_m92():
    """Beethoven Op.132/iii, Violin II m.92 (verified in the XML): [B3 G4~] then
    [C4 G4] -- G4 is tied, the other chord members are not."""
    score = load_raw_score(ROOT / "corpus" / "beethoven_op132_iii.musicxml").toSoundingPitch()
    groups, _ = tie_merged_groups(score)
    window = [(n, o, d) for n, o, d in _summ(groups, 1) if F(473, 2) <= o < F(238)]
    assert window == [("B3", F(473, 2), F(1)), ("G4", F(473, 2), F(2)), ("C4", F(475, 2), F(1))]


def _check_invariants(path):
    score = load_raw_score(path).toSoundingPitch()
    inst = collect_pitch_instances(score)
    groups, anomalies = tie_merged_groups(score)
    # duration conserved, every instance lands in exactly one group
    assert sum(len(g.members) for g in groups) == len(inst)
    assert sum(g.duration for g in groups) == sum(i.duration for i in inst)
    unterminated = {(a.stream_idx, a.midi, a.onset) for a in anomalies if a.kind == "unterminated"}
    for g in groups:
        ms = g.members
        assert len({m.midi for m in ms}) == 1 and len({m.stream_idx for m in ms}) == 1
        for a, b in zip(ms, ms[1:]):
            assert a.onset + a.duration == b.onset          # contiguous
            assert a.tie in ("start", "continue") and b.tie in ("continue", "stop")
        last = ms[-1]
        if last.tie in ("start", "continue") and not last.is_grace:
            assert (last.stream_idx, last.midi, last.onset) in unterminated
    return groups, anomalies


@pytest.mark.parametrize("name", ["beethoven_op18-2_ii", "beethoven_op132_iii", "beethoven_op18-4_i"])
def test_corpus_invariants_abc(name):
    _, anomalies = _check_invariants(ROOT / "corpus" / f"{name}.musicxml")
    assert len(anomalies) <= 3


@pytest.mark.slow
def test_corpus_invariants_grieg_raw():
    path = glob.glob(str(ROOT / "raw_corpora/StringQuartets/scores/Grieg*/String_Quartet_No.1*/*.mxl"))[0]
    groups, anomalies = _check_invariants(path)
    # 1640 before 2026-10-06; 4 tied diamond touch-points in artificial
    # harmonics are now dropped (PLAN.md decision 10)
    assert sum(g.is_tied for g in groups) == 1636
    assert len(anomalies) == 3
