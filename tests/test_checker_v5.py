"""checker-v5 (2026-10-14, from the user's review of Bridge bars 60-75): triple stops need normal hand position
(violin/viola stretch <= 4 semitones) and at least a quarter before the next note in the part (triple_recover).
Golden case: bar 75, violin G3 + Eb4 + Eb5 as an eighth, then D5. Plus batch == incremental == growing."""
import random
from fractions import Fraction as F

import numpy as np
import pytest

from arrangement.checker import IncrementalChecker, check
from arrangement.checker.types import NoteArrays
from arrangement.decode.growing import GrowingChecker
from arrangement.instruments import load_ensemble

TRIO = load_ensemble("trio")
VN, VA, VC = 0, 1, 2


def run(ens, notes):
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    return check(na, ens, np.array([n[3] for n in notes]))


def kinds(vs):
    return sorted({v.check for v in vs})


def test_bar75_chord_is_unplayable_for_both_reasons():
    chord = [(0, F(1, 2), 55, VN), (0, F(1, 2), 63, VN), (0, F(1, 2), 75, VN)]   # open G, low-1 Eb4, extended-4 Eb5
    ks = kinds(run(TRIO, chord + [(F(1, 2), F(1, 2), 74, VN)]))
    assert "triple_stretch" in ks and "triple_recover" in ks


def test_normal_position_triple_with_time_is_fine():
    # G3 D4 B4 (open, open, 2nd finger) struck as an eighth (a held triple trips the bow rule), then a rest
    chord = [(0, F(1, 2), 55, VN), (0, F(1, 2), 62, VN), (0, F(1, 2), 71, VN)]
    assert kinds(run(TRIO, chord + [(1, F(1, 2), 74, VN)])) == []


def test_triple_recover_only():
    chord = [(0, F(1, 2), 55, VN), (0, F(1, 2), 62, VN), (0, F(1, 2), 71, VN)]
    assert kinds(run(TRIO, chord + [(F(1, 2), F(1, 2), 74, VN)])) == ["triple_recover"]
    assert kinds(run(TRIO, chord + [(1, F(1, 2), 74, VN)])) == []                # a rest after it gives the time


def test_cello_stretch_unchanged_at_4():
    sp = TRIO.instruments[VC].strings
    assert sp.triple_max_stretch == 4 and TRIO.instruments[VN].strings.triple_max_stretch == 4


def _random(seed, ens):
    rng = random.Random(seed)
    notes, t = [], F(0)
    for _ in range(rng.randrange(5, 60)):
        t += rng.choice([0, 0, 0, F(1, 4), F(1, 2), F(1, 3), 1])
        notes.append((t, rng.choice([F(1, 4), F(1, 2), 1, 2]), rng.choice([rng.randrange(40, 85), 55, 62, 69]),
                      rng.randrange(len(ens))))
    return notes


@pytest.mark.parametrize("ens_name", ["trio", "quartet", "duo", "solo_violin"])
@pytest.mark.parametrize("seed", range(30))
def test_batch_equals_incremental_v5(ens_name, seed):
    ens = load_ensemble(ens_name)
    notes = _random(seed, ens)
    rng = random.Random(seed + 11)
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    a = np.array([n[3] for n in notes])
    want = check(na, ens, a)
    order = list(range(len(notes)))
    rng.shuffle(order)
    ck = IncrementalChecker(na, ens)
    for i in order:
        ck.commit(i, int(a[i]))
    assert ck.violations() == want
    for i in order[: len(order) // 2]:
        ck.uncommit(i)
    left = a.copy()
    left[order[: len(order) // 2]] = -1
    assert ck.violations() == check(na, ens, left)


def test_random_cases_exercise_v5():
    seen = set()
    for seed in range(30):
        seen |= {v.check for v in run(TRIO, _random(seed, TRIO))}
    assert "triple_recover" in seen


@pytest.mark.parametrize("seed", range(20))
def test_growing_equals_batch_v5(seed):
    notes = _random(seed, TRIO)
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    g = GrowingChecker(TRIO, na.tpq, int((na.end - na.onset).max()))
    for k in range(len(notes)):
        g.add(int(na.onset[k]), int(na.end[k]), int(na.pitch[k]), int(notes[k][3]))
    assert g.violations() == check(na, TRIO, np.array([n[3] for n in notes]))
