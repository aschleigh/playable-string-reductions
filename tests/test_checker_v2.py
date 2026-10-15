"""checker-v2 rules: golden cases + batch == incremental with every v2 rule active."""
import dataclasses
import random
from fractions import Fraction as F

import numpy as np
import pytest

from arrangement.checker import IncrementalChecker, check
from arrangement.checker import rules_v2 as R2
from arrangement.checker.types import NoteArrays
from arrangement.instruments import load_ensemble


def tight(ens, d=1.0, t=2.0):
    """Ensemble with the calibrated v2 thresholds replaced by test values, so bow/shift fire."""
    insts = []
    for i in ens.instruments:
        if i.strings is not None:
            i = dataclasses.replace(i, strings=dataclasses.replace(i.strings, bow_sustain_max_dur=d, shift_min_time=t))
        insts.append(i)
    return dataclasses.replace(ens, instruments=tuple(insts))


def run(ens, notes):
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    return check(na, ens, np.array([n[3] for n in notes]))


TRIO = tight(load_ensemble("trio"))
VN, VA, VC = 0, 1, 2


def kinds(vs):
    return sorted({v.check for v in vs})


def test_user_cello_chord_is_unplayable():
    # B2 F4 G4 B4 on cello: no one-string-per-note placement within one hand position
    # (checker-v3 adds triple_stretch, the tighter 3+-note limit)
    assert kinds(run(TRIO, [(0, F(1, 2), x, VC) for x in (47, 65, 67, 71)])) == ["multistop", "triple_stretch"]


def test_playable_double_stops_pass():
    for chord in [(43, 50), (50, 57), (48, 55, 62), (36, 52)]:   # fifths, open strings, C2 + E3 (open + 4)
        assert "multistop" not in kinds(run(TRIO, [(0, F(1, 2), x, VC) for x in chord])), chord


def test_unison_on_two_strings_is_allowed_but_not_on_one():
    assert "multistop" not in kinds(run(TRIO, [(0, 1, 69, VN), (0, 1, 69, VN)]))   # open A + A on D string
    assert "multistop" in kinds(run(TRIO, [(0, 1, 55, VN), (0, 1, 55, VN)]))       # G3 exists only on the G string


def test_skipping_a_string_is_forbidden():
    # violin G3 exists only on the G string; A6 (93) is above the D string's reach,
    # so it needs the A or E string: never adjacent to G
    assert "multistop" in kinds(run(TRIO, [(0, 1, 55, VN), (0, 1, 93, VN)]))
    # G3 + E5 is fine: open G with E5 on the D string
    assert "multistop" not in kinds(run(TRIO, [(0, 1, 55, VN), (0, 1, 76, VN)]))


def test_stretch_limit_is_k():
    sp = TRIO.instruments[VC].strings
    assert R2.placement((45, 59), sp.open, sp.max_offset, 7)[0]        # A2 (C+9) & B3 (G+16)?  feasible somewhere
    ok, st = R2.placement((47, 74), sp.open, sp.max_offset, 7)         # B2 and D5 on adjacent strings
    assert not ok and st > 7


def test_bow_three_sustained_notes():
    assert kinds(run(TRIO, [(0, 4, x, VC) for x in (36, 43, 50)])) == ["bow"]
    assert "bow" not in kinds(run(TRIO, [(0, F(1, 2), x, VC) for x in (36, 43, 50)]))   # short triple stop


def test_shift_needs_time():
    # C#2 exists only on the C string (offset 1); E5 needs offset >= 19: a move of >= 18 in a 16th
    fast = [(0, F(1, 4), 37, VC), (F(1, 4), F(1, 4), 76, VC)]
    assert "shift" in kinds(run(TRIO, fast))
    slow = [(0, F(1, 4), 37, VC), (4, F(1, 4), 76, VC)]
    # E3 -> E5 is only a 10-semitone move (G string to A string)
    assert "shift" not in kinds(run(TRIO, [(0, F(1, 4), 52, VC), (F(1, 4), F(1, 4), 76, VC)]))
    assert "shift" not in kinds(run(TRIO, slow))


def test_open_string_frees_the_hand():
    assert "shift" not in kinds(run(TRIO, [(0, F(1, 4), 36, VC), (F(1, 4), F(1, 4), 76, VC)]))


def test_piano_duplicate_and_hand_leap():
    pf = load_ensemble("piano")
    assert kinds(run(pf, [(0, 2, 60, 0), (1, 2, 60, 0)])) == ["duplicate"]
    # one low and one high note can be split between the hands: no leap
    assert "hand_leap" not in kinds(run(pf, [(0, F(1, 4), 30, 0), (F(1, 4), F(1, 4), 100, 0)]))
    # both hands busy, then both jump ~30 semitones in a 16th (allowed 24 + 12/4 = 27)
    assert "hand_leap" in kinds(run(pf, [(0, F(1, 4), 30, 0), (0, F(1, 4), 90, 0),
                                         (F(1, 4), F(1, 4), 60, 0), (F(1, 4), F(1, 4), 62, 0)]))
    assert "hand_leap" not in kinds(run(pf, [(0, F(1, 4), 60, 0), (F(1, 4), F(1, 4), 64, 0)]))


def test_flute_unaffected_by_string_rules():
    fl = load_ensemble("solo_flute")
    assert all(v.check in ("simultaneity", "range") for v in run(fl, [(0, 1, 72, 0), (0, 1, 76, 0), (1, 1, 74, 0)]))


@pytest.mark.parametrize("ens_name", ["trio", "quartet", "duo", "piano"])
@pytest.mark.parametrize("seed", range(25))
def test_batch_equals_incremental_v2(ens_name, seed):
    rng = random.Random(seed)
    ens = tight(load_ensemble(ens_name))
    notes, t = [], F(0)
    for _ in range(rng.randrange(5, 70)):
        t += rng.choice([0, 0, 0, F(1, 4), F(1, 2), F(1, 3)])
        notes.append((t, rng.choice([F(1, 4), F(1, 2), 1, 2, 3]), rng.randrange(36, 96), rng.randrange(len(ens))))
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    a = np.array([n[3] for n in notes])
    want = check(na, ens, a)
    order = list(range(len(notes)))
    rng.shuffle(order)
    ck = IncrementalChecker(na, ens)
    for i in order:
        ck.commit(i, int(a[i]))
    assert ck.violations() == want
