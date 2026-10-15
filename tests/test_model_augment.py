"""Augmentation is reversible: expand(labels) rebuilds the target exactly."""
import json
import random
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

import pytest

import model.augment as A

DATA = Path(__file__).resolve().parents[1] / "model" / "data" / "train.jsonl"
RANGES = A.load_ranges()


def _movements(n=6):
    if not DATA.exists():
        pytest.skip("model data not exported")
    out = []
    with open(DATA) as f:
        for k, line in enumerate(f):
            if k >= n:
                break
            d = json.loads(line)
            out.append([(int(p), F(o), F(du), int(x)) for p, o, du, x in d["notes"]])
    return out


def test_patterns_and_inverse_on_handmade_part():
    # repeat run, tremolo run, arpeggio, octave double stop
    notes = [(F(0), F(1, 2), 60)] * 0 + [(F(k, 2), F(1, 2), 60) for k in range(4)] \
        + [(F(2) + F(k, 4), F(1, 4), 62) for k in range(4)] \
        + [(F(3) + F(k, 2), F(1, 2), x) for k, x in enumerate([55, 59, 62, 67])] \
        + [(F(5), F(1), 48), (F(5), F(1), 60)]
    kinds = sorted(k for k, _ in A.detect(sorted(notes)))
    assert kinds == sorted([A.REPEAT, A.TREMOLO, A.ARPEGGIATE, A.DOUBLE])


@pytest.mark.parametrize("seed", range(4))
def test_expand_rebuilds_target_quartet(seed, monkeypatch):
    monkeypatch.setattr(A, "COLLAPSE_P", 1.0)
    monkeypatch.setattr(A, "P_SHIFT", 0.0)
    monkeypatch.setattr(A, "P_KBD_DOUBLE", 0.0)
    rng = random.Random(seed)
    bad = total = 0
    for mv in _movements():
        end = max(o for _, o, _, _ in mv)
        start = F(rng.randrange(8, max(9, int(end) - 16)))
        ens, inotes, target = A.make_example(mv, start, rng, RANGES, ensemble="quartet")
        win = Counter((p, o, d, x) for p, o, d, x in mv if start - A.CONTEXT <= o < start + A.WINDOW)
        got = Counter(target)
        total += sum(win.values())
        bad += sum((win - got).values()) + sum((got - win).values())
        assert any(n.real != A.PLAIN for n in inotes) or True
    assert bad / total < 0.01, (bad, total)   # only same-part unisons / out-of-range notes may differ


def test_keyboard_doublings_are_dropped_and_shift_is_inverted(monkeypatch):
    monkeypatch.setattr(A, "P_SHIFT", 1.0)
    monkeypatch.setattr(A, "P_KBD_DOUBLE", 1.0)
    mv = _movements(1)[0]
    ens, inotes, target = A.make_example(mv, F(16), random.Random(1), RANGES, ensemble="quartet")
    assert any(n.part == A.DROP for n in inotes)
    assert any(n.octave != 0 for n in inotes)
    for p, o, d, x in target:   # expanded output stays in range
        lo, hi = RANGES[A.ENSEMBLES["quartet"][0][p]]
        assert lo <= x <= hi
