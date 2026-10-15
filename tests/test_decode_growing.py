"""GrowingChecker == batch checker on the same notes, whatever the insertion order."""
import random

import numpy as np
import pytest

from arrangement.checker import check
from arrangement.checker.types import NoteArrays
from arrangement.decode.growing import GrowingChecker
from arrangement.instruments import load_ensemble


@pytest.mark.parametrize("ens_name", ["trio", "duo", "solo_flute", "piano"])
@pytest.mark.parametrize("seed", range(15))
def test_growing_matches_batch(ens_name, seed):
    rng = random.Random(seed)
    ens = load_ensemble(ens_name)
    tpq = 12
    notes = []
    for _ in range(rng.randrange(5, 120)):
        on = rng.randrange(0, 200)
        notes.append((on, on + rng.choice([1, 3, 6, 12, 24, 48]), rng.randrange(30, 100), rng.randrange(len(ens))))
    order = list(range(len(notes)))
    rng.shuffle(order)
    g = GrowingChecker(ens, tpq, max_dur_ticks=48)
    ids = {}
    for k in order:
        on, en, p, part = notes[k]
        pred = g.would_add(on, en, p, part)
        i, added = g.add(on, en, p, part)
        assert set(pred) == set(added)
        ids[k] = i
    arr = NoteArrays(onset=np.array([n[0] for n in notes]), end=np.array([n[1] for n in notes]),
                     pitch=np.array([n[2] for n in notes]), grace=np.zeros(len(notes), bool), tpq=tpq)
    want = check(arr, ens, np.array([n[3] for n in notes]))
    remap = {i: k for k, i in ids.items()}
    got = sorted((v.check, v.part_id, tuple(sorted(remap[i] for i in v.note_ids))) for v in g.violations())
    assert got == sorted((v.check, v.part_id, tuple(sorted(v.note_ids))) for v in want)
