"""checker-v8 (R83): piano hand gap (a minor third between the hands), spans up to an octave free, 9th/10th only after
a set-up time. Incremental == batch == growing on random piano music, for both gap bases; unit cases."""
import random
from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from arrangement.checker import IncrementalChecker, UNASSIGNED, check
from arrangement.checker.types import NoteArrays
from arrangement.decode.growing import GrowingChecker
from arrangement.instruments import load_ensemble
from checker_helpers import build
from test_piano_struck import random_piano


def piano(gap_basis="sounding", setup=0.5):
    ens = load_ensemble("piano")
    inst = ens.instruments[0]
    hs = replace(inst.hand_span, basis="struck", semitones=16, free_semitones=12, setup_q=setup, gap=3, gap_basis=gap_basis)
    return replace(ens, instruments=(replace(inst, hand_span=hs),))


def kinds(ens, notes):
    na, assign = build(notes)
    return [v.check for v in check(na, ens, assign)]


@pytest.mark.parametrize("basis", ["struck", "sounding"])
@pytest.mark.parametrize("seed", range(40))
def test_incremental_matches_batch(basis, seed):
    rng = random.Random(seed)
    ens = piano(basis)
    notes, assign = random_piano(rng, rng.randrange(5, 70))
    order = [i for i in range(len(assign)) if assign[i] != UNASSIGNED]
    rng.shuffle(order)
    ck = IncrementalChecker(notes, ens)
    for i in order:
        ck.commit(i, int(assign[i]))
    assert ck.violations() == check(notes, ens, assign)
    for i in order[: len(order) // 2]:          # removal keeps it a pure function of the assignment
        ck.uncommit(i)
        assign[i] = UNASSIGNED
    assert ck.violations() == check(notes, ens, assign)


@pytest.mark.parametrize("basis", ["struck", "sounding"])
@pytest.mark.parametrize("seed", range(20))
def test_growing_matches_batch(basis, seed):
    rng = random.Random(100 + seed)
    ens = piano(basis)
    notes = []
    for _ in range(rng.randrange(5, 100)):
        on = rng.randrange(0, 150)
        notes.append((on, on + rng.choice([3, 6, 12, 48]), rng.randrange(28, 100), 0))
    order = list(range(len(notes)))
    rng.shuffle(order)
    g = GrowingChecker(ens, 12, max_dur_ticks=48)
    ids = {}
    for k in order:
        on, en, p, part = notes[k]
        pred = g.would_add(on, en, p, part)
        i, added = g.add(on, en, p, part)
        assert set(pred) == set(added)
        ids[k] = i
    arr = NoteArrays(onset=np.array([n[0] for n in notes]), end=np.array([n[1] for n in notes]),
                     pitch=np.array([n[2] for n in notes]), grace=np.zeros(len(notes), bool), tpq=12)
    want = check(arr, ens, np.array([n[3] for n in notes]))
    remap = {i: k for k, i in ids.items()}
    got = sorted((v.check, v.part_id, tuple(sorted(remap[i] for i in v.note_ids))) for v in g.violations())
    assert got == sorted((v.check, v.part_id, tuple(sorted(v.note_ids))) for v in want)


F0, Q = Fraction(0), Fraction(1)


def test_gap_held_left_hand_note():
    # E4 held from beat 0; then C3 C4 D4 struck with F4 A4 C5 E5. With the held E4 between D4 and F4 the hands cannot be a
    # minor third apart within five fingers and a tenth ("sounding"); without it, D4 | F4 is a minor third ("struck")
    notes = [(F0, 4 * Q, 64, 0, False)] + [(Q, Q, x, 0, False) for x in (48, 60, 62, 65, 69, 72, 76)]
    assert "hand_span" in kinds(piano("sounding"), notes)
    assert "hand_span" not in kinds(piano("struck"), notes)


def test_gap_moves_note_to_right_hand():
    # C3 E3 G4 | B4 D5 struck together: G4 can join the right hand (G4-D5 is a fifth), so the gap is met
    assert "hand_span" not in kinds(piano(), [(F0, Q, x, 0, False) for x in (48, 52, 67, 71, 74)])


def test_setup_time_for_a_tenth():
    # C2-C3 and C4-E5 struck together: the only split leaves the right hand a tenth (16)
    chord = [(x, 0, False) for x in (36, 48, 60, 64, 67, 76)]
    fast = [(F0, Q / 4, 40, 0, False)] + [(Q / 4, Q, x, p, g) for x, p, g in chord]
    slow = [(F0, Q / 4, 40, 0, False)] + [(Q, Q, x, p, g) for x, p, g in chord]
    ens = piano(setup=0.5)
    assert "hand_span" in kinds(ens, fast)
    assert "hand_span" not in kinds(ens, slow)
    assert "hand_span" in kinds(ens, [(F0, Q, x, 0, False) for x in (36, 48, 60, 64, 67, 77)])   # an 11th: never
