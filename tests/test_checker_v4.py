"""checker-v4 rules (double_onset, restrike, double_rate): golden cases taken from the
user's review of the checker-v3-masked trio (movement 067), plus batch == incremental."""
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


def test_held_note_under_moving_line():
    # violin bar 4: D4 held while 32nds G4 F#4 G4 move above it
    notes = [(1, F(1, 2), 62, VN)] + [(1 + F(k + 1, 12), F(1, 12), x, VN) for k, x in enumerate((67, 66, 67))]
    assert "double_onset" in kinds(run(TRIO, notes))
    assert "double_onset" not in kinds(run(TRIO, notes[1:]))         # the line alone is fine


def test_struck_double_stop_is_fine():
    assert kinds(run(TRIO, [(0, 1, 62, VN), (0, 1, 69, VN)])) == []


def test_restrike_of_sounding_pitch():
    # cello bar 7: D4 held 3 beats, D4 struck again at beat 1.5
    vs = kinds(run(TRIO, [(0, 3, 62, VC), (F(3, 2), F(3, 2), 62, VC)]))
    assert "restrike" in vs and "double_onset" in vs


def test_double_stop_rate():
    sixths = [(0, F(1, 2), 71, VA), (0, F(1, 2), 74, VA), (F(1, 2), F(1, 2), 69, VA), (F(1, 2), F(1, 2), 73, VA)]
    assert kinds(run(TRIO, sixths)) == []                            # viola bar 5: 8ths, just allowed
    fast = [(F(k, 4), F(1, 4), x, VA) for k, pair in enumerate(((71, 74), (69, 73))) for x in pair]
    assert kinds(run(TRIO, fast)) == ["double_rate"]                 # 16ths: too fast
    same = [(F(k, 4), F(1, 4), x, VA) for k in range(4) for x in (71, 74)]
    assert kinds(run(TRIO, same)) == []                              # one double stop repeated in 16ths: bow only


def test_v4_does_not_touch_other_instruments():
    pf = load_ensemble("piano")
    assert kinds(run(pf, [(0, 2, 60, 0), (1, F(1, 4), 64, 0), (F(5, 4), F(1, 4), 67, 0)])) == []


def _random(seed, ens):
    rng = random.Random(seed)
    notes, t = [], F(0)
    for _ in range(rng.randrange(5, 60)):
        t += rng.choice([0, 0, F(1, 4), F(1, 2), F(1, 3), 1])
        notes.append((t, rng.choice([F(1, 4), F(1, 2), 1, 2]), rng.choice([rng.randrange(40, 85), 62, 62]),
                      rng.randrange(len(ens))))
    return notes


@pytest.mark.parametrize("ens_name", ["trio", "quartet", "duo", "solo_violin"])
@pytest.mark.parametrize("seed", range(30))
def test_batch_equals_incremental_v4(ens_name, seed):
    ens = load_ensemble(ens_name)
    notes = _random(seed, ens)
    rng = random.Random(seed + 7)
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


def test_random_cases_exercise_v4():
    seen = set()
    for seed in range(30):
        seen |= {v.check for v in run(TRIO, _random(seed, TRIO))}
    assert {"double_onset", "restrike", "double_rate"} <= seen


@pytest.mark.parametrize("seed", range(20))
def test_growing_equals_batch_v4(seed):
    notes = _random(seed, TRIO)
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    g = GrowingChecker(TRIO, na.tpq, int((na.end - na.onset).max()))
    for k in range(len(notes)):
        g.add(int(na.onset[k]), int(na.end[k]), int(na.pitch[k]), int(notes[k][3]))
    assert g.violations() == check(na, TRIO, np.array([n[3] for n in notes]))
