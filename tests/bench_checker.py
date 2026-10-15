"""Checker benchmark. Run: python tests/bench_checker.py

Synthetic quartet movements at real-corpus sizes (the Haydn Op.51 first
movement is ~1,700 notes). Two assignments per size: 'lines' (each part a
plausible line, few violations) and 'random' (ceiling-like, many violations;
the costly case for violation gathering). Target: full check < 10 ms/movement.
"""
from __future__ import annotations

import random
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from arrangement.checker import IncrementalChecker, NoteArrays, check  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402

BASES = [76, 69, 60, 48]


def movement(n: int, seed: int):
    rng = random.Random(seed)
    on, du, pi, part = [], [], [], []
    per = n // 4
    for p in range(4):
        t, x = Fraction(0), BASES[p]
        for _ in range(per):
            d = rng.choice([Fraction(1, 4), Fraction(1, 2), Fraction(1, 2), Fraction(1), Fraction(1, 3)])
            x = min(max(x + rng.choice([-2, -1, 1, 2, 0, 3, -3, 7]), BASES[p] - 10), BASES[p] + 14)
            on.append(t); du.append(d); pi.append(x); part.append(p)
            if rng.random() < 0.05:   # double stop
                on.append(t); du.append(d); pi.append(x - 4); part.append(p)
            t += d
    return NoteArrays.from_notes(on, du, pi), np.array(part)


def timeit(fn, reps):
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t)
    return best


def main():
    ens = load_ensemble("quartet")
    rng = np.random.default_rng(0)
    print(f"{'notes':>6} {'assign':>7} {'viol':>6} {'batch ms':>9} {'incr all ms':>12} {'commit us':>10} {'mask us':>9}")
    for n in (500, 2000, 8000):
        notes, lines = movement(n, n)
        for name, a in (("lines", lines), ("random", rng.integers(0, 4, len(lines)))):
            nv = len(check(notes, ens, a))
            tb = timeit(lambda: check(notes, ens, a), 20)

            def incr():
                ck = IncrementalChecker(notes, ens)
                for i in range(len(a)):
                    ck.commit(i, int(a[i]))
                return ck
            ti = timeit(incr, 3)
            ck = incr()
            sample = list(range(0, len(a), max(1, len(a) // 200)))
            t = time.perf_counter()
            for i in sample:
                ck.uncommit(i); ck.mask(i); ck.commit(i, int(a[i]))
            tm = (time.perf_counter() - t) / len(sample)
            print(f"{len(a):>6} {name:>7} {nv:>6} {tb*1e3:>9.2f} {ti*1e3:>12.1f} {ti/len(a)*1e6:>10.1f} {tm*1e6:>9.0f}")


if __name__ == "__main__":
    main()
