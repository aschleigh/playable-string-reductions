"""Incremental checker == batch checker on random partial assignments, for
any commit order, with uncommits; masking leaves state untouched."""
import random
from fractions import Fraction

import numpy as np
import pytest

from arrangement.checker import IncrementalChecker, NoteArrays, UNASSIGNED, check
from checker_helpers import build, ensemble

GRID = [Fraction(1, 4), Fraction(1, 3), Fraction(1, 2), Fraction(1)]


def random_piece(rng: random.Random, n: int, n_parts: int, unassigned=0.2, dense=False, grace_p=0.05):
    notes, t = [], Fraction(0)
    steps = [0, 0, 0, 0, 0, Fraction(1, 2)] if dense else [0, 0, Fraction(1, 4), Fraction(1, 3), Fraction(1, 2)]
    for _ in range(n):
        t += rng.choice(steps)
        grace = rng.random() < grace_p
        dur = Fraction(0) if grace else rng.choice(GRID) * rng.choice([1, 1, 2, 3])
        part = UNASSIGNED if rng.random() < unassigned else rng.randrange(n_parts)
        notes.append((t, dur, rng.randrange(30, 110), part, grace))
    return build(notes)


@pytest.mark.parametrize("basis", ["release", "onset"])
@pytest.mark.parametrize("dense", [False, True])
@pytest.mark.parametrize("ens_name", ["test", "quartet"])
@pytest.mark.parametrize("seed", range(40))
def test_any_commit_order_matches_batch(ens_name, seed, dense, basis):
    rng = random.Random(seed)
    ens = ensemble(ens_name, basis)
    notes, assign = random_piece(rng, rng.randrange(5, 60), len(ens), dense=dense)
    expected = check(notes, ens, assign)
    order = [i for i in range(len(assign)) if assign[i] != UNASSIGNED]
    rng.shuffle(order)
    ck = IncrementalChecker(notes, ens)
    for k, i in enumerate(order):
        d = ck.commit(i, int(assign[i]))
        for v in d.added:                     # a commit only adds violations involving that note
            assert i in v.note_ids
        partial = np.full(len(assign), UNASSIGNED)
        partial[order[:k + 1]] = assign[order[:k + 1]]
        if k % 7 == 0 or k == len(order) - 1:  # every prefix is itself a valid partial check
            assert ck.violations() == check(notes, ens, partial)
    assert ck.violations() == expected


@pytest.mark.parametrize("basis", ["release", "onset"])
@pytest.mark.parametrize("ens_name", ["test", "quartet"])
@pytest.mark.parametrize("seed", range(30))
def test_grace_heavy_matches_batch(ens_name, seed, basis):
    rng = random.Random(5000 + seed)
    ens = ensemble(ens_name, basis)
    notes, assign = random_piece(rng, rng.randrange(10, 80), len(ens), dense=seed % 2 == 0, grace_p=0.35)
    ck = IncrementalChecker(notes, ens)
    order = [i for i in range(len(assign)) if assign[i] != UNASSIGNED]
    rng.shuffle(order)
    for i in order:
        ck.commit(i, int(assign[i]))
    assert ck.violations() == check(notes, ens, assign)


@pytest.mark.parametrize("seed", range(20))
def test_uncommit_and_reassign(seed):
    rng = random.Random(1000 + seed)
    ens = ensemble("test")
    notes, assign = random_piece(rng, 40, len(ens), unassigned=0.0, dense=seed % 2 == 0)
    ck = IncrementalChecker(notes, ens)
    cur = np.full(len(assign), UNASSIGNED)
    for _ in range(150):
        i = rng.randrange(len(assign))
        if cur[i] == UNASSIGNED:
            p = rng.randrange(len(ens))
            ck.commit(i, p)
            cur[i] = p
        else:
            ck.uncommit(i)
            cur[i] = UNASSIGNED
        assert ck.violations() == check(notes, ens, cur)


@pytest.mark.parametrize("seed", range(10))
def test_would_violate_and_mask_do_not_change_state(seed):
    rng = random.Random(2000 + seed)
    ens = ensemble("quartet")
    notes, assign = random_piece(rng, 50, len(ens), unassigned=0.5)
    ck = IncrementalChecker(notes, ens)
    for i in np.flatnonzero(assign != UNASSIGNED):
        ck.commit(int(i), int(assign[i]))
    before = ck.violations()
    for i in np.flatnonzero(assign == UNASSIGNED):
        m = ck.mask(int(i))
        for p in range(len(ens)):
            assert m[p] == (len(ck.would_violate(int(i), p)) == 0)
        assert ck.violations() == before
    assert (ck.assign == assign).all()


def test_transition_is_not_monotone():
    """Documented: a later commit can clear a transition violation by giving
    the next note a nearer predecessor released at the same time."""
    notes, _ = build([(0, 1, 55, 1), (1, 1, 100, 1), (0, 1, 90, 1)])
    ck = IncrementalChecker(notes, ensemble("test"))
    ck.commit(0, 1)
    assert [v.check for v in ck.commit(1, 1).added] == ["transition"]
    d = ck.commit(2, 1)
    assert [v.check for v in d.removed] == ["transition"] and d.added == ()


def test_double_commit_and_bad_part_rejected():
    notes, _ = build([(0, 1, 60, 0)])
    ck = IncrementalChecker(notes, ensemble("test"))
    with pytest.raises(ValueError):
        ck.commit(0, 9)
    ck.commit(0, 0)
    with pytest.raises(ValueError):
        ck.commit(0, 1)


def test_deterministic_repeated_runs():
    rng = random.Random(7)
    ens = ensemble("quartet")
    notes, assign = random_piece(rng, 200, len(ens))
    runs = [check(notes, ens, assign) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_exact_ticks_for_triplets():
    n = NoteArrays.from_notes([0, Fraction(1, 3), Fraction(2, 3)], [Fraction(1, 3)] * 3, [60, 62, 64])
    assert n.tpq == 3 and n.end.tolist() == [1, 2, 3]
    with pytest.raises(ValueError):
        NoteArrays.from_notes([0], [0], [60])        # zero duration must be grace


def test_onset_basis_counts_previous_note_duration():
    # leap 45 with no rest after a 2-quarter note: release basis allows 24,
    # onset basis allows 24 + 12*2 = 48.
    notes, assign = build([(0, 2, 55, 1), (2, 1, 100, 1)])
    assert [v.check for v in check(notes, ensemble("test", "release"), assign)] == ["transition"]
    assert check(notes, ensemble("test", "onset"), assign) == []
