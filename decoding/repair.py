"""Ou et al. + repair: a deterministic post-processing baseline (DECODING.md amendment A3).

    python -m decoding.repair [--regimes trio duo ...] [--workers N]

Input: the UNCONSTRAINED Ou et al. records (headroom/data/records/<ou_band|ou_piano>__<regime>.jsonl).
Notes are visited in time order, highest pitch first at equal onsets (so a top line is
placed before the notes under it). Each note goes to the first legal option under the frozen
checker, given everything already placed:
  1. Ou's own part, as written;
  2. the other parts, nearest in register first (distance from the pitch to the part's range);
  3. Ou's part, an octave up or down (the octave nearer the range middle first);
  4. the other parts with an octave shift, in the same orders;
  5. otherwise the note is dropped.
"Legal" = adding it creates no hard violation (GrowingChecker, the checker's own rule code).
No model, no sampling, no search beyond this fixed order.

Output: headroom/data/records/<base>_repair__<regime>.jsonl, system "<base>_repair", with
meta.repair = counts of kept / moved / octave / moved+octave / dropped.
"""
from __future__ import annotations

import argparse
import math
from collections import Counter
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

from arrangement.decode.growing import GrowingChecker
from arrangement.eval.record import ArrangementRecord, load, make_score, save
from arrangement.instruments import load_ensemble

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "headroom" / "data" / "records"


def base_system(regime: str) -> str:
    return "ou_piano" if regime == "piano" else "ou_band"


def _dist(x: int, inst) -> int:
    return max(inst.low - x, 0, x - inst.high)


def options(x: int, p: int, ens):
    """Ordered (part, pitch, kind) candidates for a note Ou wrote in part p."""
    insts = ens.instruments
    others = sorted((q for q in range(len(insts)) if q != p), key=lambda q: (_dist(x, insts[q]), q))
    mid = lambda q: (insts[q].low + insts[q].high) / 2
    octs = lambda q: sorted((x + s for s in (12, -12) if 0 <= x + s <= 127), key=lambda y: (abs(y - mid(q)), y))
    yield p, x, "kept"
    for q in others:
        yield q, x, "moved"
    for y in octs(p):
        yield p, y, "octave"
    for q in others:
        for y in octs(q):
            yield q, y, "moved+octave"


def repair(r: ArrangementRecord) -> ArrangementRecord:
    ens = load_ensemble(r.ensemble)
    notes = sorted(r.output.notes, key=lambda n: (n[1], -n[3], n[0], n[2]))
    tpq = 1
    for _, o, d, _ in notes:
        tpq = math.lcm(tpq, Fraction(o).denominator, Fraction(d).denominator)
    max_dur = max((int(d * tpq) for _, _, d, _ in notes), default=1)
    ck = GrowingChecker(ens, tpq, max_dur, capacity=len(notes) + 16)
    kept, counts = [], Counter()
    for p, o, d, x in notes:
        on, en = int(o * tpq), int((o + d) * tpq)
        grace = d == 0
        for q, y, kind in options(x, p, ens):
            if not ck.would_add(on, en, y, q, grace):
                ck.add(on, en, y, q, grace)
                kept.append((q, o, d, y))
                counts[kind] += 1
                break
        else:
            counts["dropped"] += 1
    parts = [(pd.name, pd.instrument) for pd in r.output.parts]
    return ArrangementRecord(system=f"{r.system}_repair", seed=r.seed, input_id=r.input_id, ensemble=r.ensemble,
                             source=r.source, output=make_score(parts, kept), bars=r.bars,
                             reference_source_parts=r.reference_source_parts, window=r.window,
                             meta={**r.meta, "repair": dict(counts)})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", nargs="+", default=["trio", "duo", "solo_violin", "solo_flute", "piano"])
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    for regime in a.regimes:
        bs = base_system(regime)
        recs = load(REC / f"{bs}__{regime}.jsonl")
        with Pool(a.workers) as pool:
            out = pool.map(repair, recs, chunksize=1)
        save(out, REC / f"{bs}_repair__{regime}.jsonl")
        tot = Counter()
        for x in out:
            tot.update(x.meta["repair"])
        n = sum(tot.values())
        print(regime, {k: f"{v} ({100 * v / n:.1f}%)" for k, v in sorted(tot.items())}, flush=True)


if __name__ == "__main__":
    main()
