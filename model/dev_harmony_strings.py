"""Block 7 Step 4.2 tie-break (R82): dev harmony (beat chroma cosine, as model/dev_fk.py) of the masked, melody-first
decodes of control-S2c, rl8-S2 and rl8-S4, trio and duo, 61 dev movements.

    python -m model.dev_harmony_strings [--workers 14]   -> model/results/rl/dev_harmony_rl8.json
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np

from model.dev_fk import _W, _init, harmony

ROOT = Path(__file__).resolve().parents[1]
RUNS = ["control-S2c", "rl8-S2", "rl8-S4"]


def _job(job):
    key, regime = job
    import model.augment as A
    from arrangement.instruments import load_ensemble
    from model.decode import decode_movement
    m = _W["val"][key]
    ens = load_ensemble(regime)
    inotes, _ = decode_movement(_W["net"], "cpu", m.src, [i.key for i in ens.instruments], ens, True, m.tpq, True)
    return regime, key, harmony(A.expand(inotes), m.src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    res = {}
    for run in RUNS:
        ck = ROOT / "model" / "results" / "rl" / run / "checkpoint.pt"
        _init(None)
        keys = sorted(_W["val"])
        with mp.get_context("fork").Pool(a.workers, initializer=_init, initargs=(str(ck),)) as pool:
            rows = pool.map(_job, [(k, r) for r in ("trio", "duo") for k in keys], chunksize=1)
        res[run] = {r: {k: h for rr, k, h in rows if rr == r} for r in ("trio", "duo")}
        print(run, {r: round(float(np.mean(list(v.values()))), 4) for r, v in res[run].items()}, flush=True)
    out = {"per_movement": res, "mean": {run: {r: float(np.mean(list(v.values()))) for r, v in d.items()} for run, d in res.items()},
           "mean_trio_duo": {run: float(np.mean([np.mean(list(v.values())) for v in d.values()])) for run, d in res.items()}}
    (ROOT / "model" / "results" / "rl" / "dev_harmony_rl8.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["mean"], indent=1), json.dumps(out["mean_trio_duo"]))


if __name__ == "__main__":
    main()
