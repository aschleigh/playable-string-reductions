"""checker-v3 rules (triple_onset, triple_stretch, triple_rate, bow d = 0.5): golden cases
with the shipped config, plus batch == incremental == growing with every v3 rule active."""
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


def test_struck_triple_stop_alone_is_fine():
    # cello G2 D3 A3: open G, open D, open A, short
    assert kinds(run(TRIO, [(0, F(1, 2), x, VC) for x in (43, 50, 57)])) == []


def test_fast_succession_of_triple_stops():
    chords = [(43, 50, 57), (43, 50, 59)]           # second chord a quarter-beat later
    fast = [(F(k, 4), F(1, 4), x, VC) for k, c in enumerate(chords) for x in c]
    assert kinds(run(TRIO, fast)) == ["double_rate", "triple_rate", "triple_recover"]   # v4: double_rate; v5: recover
    slow = [(k, F(1, 4), x, VC) for k, c in enumerate(chords) for x in c]   # one beat apart
    assert kinds(run(TRIO, slow)) == []


def test_overlapping_run_is_not_a_chord():
    # the bar-13 pattern: a scale whose notes are written longer than their spacing,
    # so three strings would have to sound without being struck together
    run_notes = [(F(k, 4), F(1, 3) + F(1, 4), x, VC) for k, x in enumerate((57, 59, 61, 62))]
    assert "triple_onset" in kinds(run(TRIO, run_notes))
    # the same scale written cleanly: no v3 violation
    clean = [(F(k, 4), F(1, 4), x, VC) for k, x in enumerate((57, 59, 61, 62))]
    assert not any(v.check.startswith("triple") for v in run(TRIO, clean))


def test_held_note_under_a_new_double_stop():
    notes = [(0, 2, 43, VC), (1, F(1, 2), 50, VC), (1, F(1, 2), 57, VC)]
    assert "triple_onset" in kinds(run(TRIO, notes))
    assert "triple_onset" not in kinds(run(TRIO, notes[1:]))       # a double stop alone is fine


def test_triple_stretch_tighter_than_double_stop_stretch():
    # violin E4 B4 G5: G string? no: E4 on D string (+2), B4 on A string (+2), G5 on E string (+3): stretch 1
    assert "triple_stretch" not in kinds(run(TRIO, [(0, F(1, 2), x, VN) for x in (64, 71, 79)]))
    # violin C#5 D5 E5 (the tight cluster in bar 12): open E, D5 on A (+5), C#5 on D (+11): stretch 6 > 5
    vs = run(TRIO, [(0, F(1, 2), x, VN) for x in (73, 74, 76)])
    assert "triple_stretch" in kinds(vs) and "multistop" not in kinds(vs)   # 6 <= 9 as a double-stop limit


def test_bow_half_beat():
    assert "bow" in kinds(run(TRIO, [(0, 1, x, VC) for x in (43, 50, 57)]))           # three held a beat
    assert "bow" not in kinds(run(TRIO, [(0, F(1, 2), x, VC) for x in (43, 50, 57)]))  # half a beat: allowed


def _random(seed, ens):
    rng = random.Random(seed)
    notes, t = [], F(0)
    for _ in range(rng.randrange(5, 70)):
        t += rng.choice([0, 0, 0, F(1, 4), F(1, 2), F(1, 3)])
        notes.append((t, rng.choice([F(1, 4), F(1, 2), 1, 2]), rng.randrange(36, 90), rng.randrange(len(ens))))
    return notes


@pytest.mark.parametrize("ens_name", ["trio", "quartet", "duo", "solo_violin"])
@pytest.mark.parametrize("seed", range(30))
def test_batch_equals_incremental_v3(ens_name, seed):
    ens = load_ensemble(ens_name)
    notes = _random(seed, ens)
    rng = random.Random(seed + 1000)
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    a = np.array([n[3] for n in notes])
    want = check(na, ens, a)
    order = list(range(len(notes)))
    rng.shuffle(order)
    ck = IncrementalChecker(na, ens)
    for i in order:
        ck.commit(i, int(a[i]))
    assert ck.violations() == want
    for i in order[: len(order) // 2]:            # uncommit restores the batch result of what is left
        ck.uncommit(i)
    left = a.copy()
    left[order[: len(order) // 2]] = -1
    assert ck.violations() == check(na, ens, left)


def test_random_cases_exercise_v3():
    seen = set()
    for seed in range(30):
        ens = load_ensemble("trio")
        notes = _random(seed, ens)
        seen |= {v.check for v in run(ens, notes)}
    assert {"triple_onset", "triple_stretch", "triple_rate"} <= seen


@pytest.mark.parametrize("seed", range(20))
def test_growing_equals_batch_v3(seed):
    ens = load_ensemble("trio")
    notes = _random(seed, ens)
    tpq = 12
    na = NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])
    g = GrowingChecker(ens, na.tpq, int((na.end - na.onset).max()))
    for k in range(len(notes)):
        g.add(int(na.onset[k]), int(na.end[k]), int(na.pitch[k]), int(notes[k][3]))
    assert g.violations() == check(na, ens, np.array([n[3] for n in notes]))
