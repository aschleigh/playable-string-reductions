"""checker-v6 (R65): keyboard hand rules on the notes struck together. Incremental == batch == growing on
random piano music with basis "struck"; a held bass note under a far right-hand chord is fine under
"struck" and a hand_span violation under "sounding"."""
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


def piano(basis: str, span: int = 16):
    ens = load_ensemble("piano")
    inst = ens.instruments[0]
    inst = replace(inst, hand_span=replace(inst.hand_span, basis=basis, semitones=span, gap=None))   # the v6 rules (v8 off)
    return replace(ens, instruments=(inst,))


def random_piano(rng, n):
    notes, t = [], Fraction(0)
    for _ in range(n):
        t += rng.choice([0, 0, 0, Fraction(1, 4), Fraction(1, 2), Fraction(1)])
        dur = rng.choice([Fraction(1, 4), Fraction(1, 2), Fraction(1), Fraction(4)])
        part = UNASSIGNED if rng.random() < 0.15 else 0
        notes.append((t, dur, rng.randrange(28, 100), part, False))
    return build(notes)


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


@pytest.mark.parametrize("seed", range(20))
def test_growing_matches_batch_struck(seed):
    rng = random.Random(100 + seed)
    ens = piano("struck")
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


def test_held_bass_under_far_chord():
    # C2 and G3 held while the right hand strikes C5-E5-G5: the sounding set {C2, G3, C5, E5, G5} has no two-hand
    # split within 16 semitones, but the struck chord alone (a fifth) is easy
    held = [(Fraction(0), Fraction(4), 36, 0, False), (Fraction(0), Fraction(4), 55, 0, False)]
    chord = [(Fraction(1), Fraction(1), x, 0, False) for x in (72, 76, 79)]
    notes, assign = build(held + chord)
    assert "hand_span" not in [v.check for v in check(notes, piano("struck"), assign)]
    assert "hand_span" in [v.check for v in check(notes, piano("sounding"), assign)]
    # a struck chord wider than two hands of 16 semitones is still a violation
    notes, assign = build([(Fraction(0), Fraction(1), x, 0, False) for x in (30, 50, 70, 90)])
    assert "hand_span" in [v.check for v in check(notes, piano("struck"), assign)]
