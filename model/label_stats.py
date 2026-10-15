"""Label statistics of the training examples (Step 2 report).

    python -m model.label_stats [--n 20000]
Writes model/results/label_stats.json.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

import model.augment as A

ROOT = Path(__file__).resolve().parents[1]


def load_movements(split="train"):
    out = []
    with open(ROOT / "model" / "data" / f"{split}.jsonl") as f:
        for line in f:
            d = json.loads(line)
            out.append([(int(p), F(o), F(du), int(x)) for p, o, du, x in d["notes"]])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    a = ap.parse_args(argv)
    mvs = load_movements()
    rng = random.Random(0)
    ranges = A.load_ranges()
    real, octv, part, ens_c = Counter(), Counter(), Counter(), Counter()
    win_any = 0
    real_by_ens = {e: Counter() for e in A.ENSEMBLES}
    detected = Counter()
    for _ in range(a.n):
        mv = rng.choice(mvs)
        end = max(o for _, o, _, _ in mv)
        start = F(rng.randrange(0, max(1, int(end) - 4)))
        ens, inotes, _ = A.make_example(mv, start, rng, ranges)
        ens_c[ens] += 1
        tgt = [n for n in inotes if not n.context]
        real.update(n.real for n in tgt)
        real_by_ens[ens].update(n.real for n in tgt)
        octv.update(n.octave for n in tgt)
        part.update("drop" if n.part == A.DROP else "kept" for n in tgt)
        win_any += any(n.real != A.PLAIN for n in tgt)
    # instances present in the corpus (before the 0.5 collapse coin)
    for mv in mvs:
        for sp in range(4):
            for kind, ids in A.detect(sorted((o, d, x) for p, o, d, x in mv if p == sp)):
                detected[A.REAL_NAMES[kind]] += len(ids)
    tot = sum(real.values())
    res = {"n_windows": a.n, "n_predicted_notes": tot, "ensembles": dict(ens_c),
           "realisation": {A.REAL_NAMES[k]: v / tot for k, v in sorted(real.items())},
           "realisation_non_plain": 1 - real[A.PLAIN] / tot,
           "realisation_non_plain_by_ensemble": {e: 1 - c[A.PLAIN] / max(1, sum(c.values())) for e, c in real_by_ens.items()},
           "windows_with_any_non_plain": win_any / a.n,
           "octave": {str(k): v / tot for k, v in sorted(octv.items())},
           "drop": part["drop"] / tot,
           "corpus_notes_in_detected_figuration": dict(detected),
           "corpus_total_notes": sum(len(m) for m in mvs)}
    (ROOT / "model" / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "model" / "results" / "label_stats.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
