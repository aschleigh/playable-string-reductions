"""Dev-split output notes for scoring with P (BLOCK5.md Steps 1c and 3): masked greedy decode (model/decode.py,
melody-first, checker-v5) of the dev movements, trio and duo, saved as expanded output notes.

    python -m model.dev_outputs --runs arranger-v2b rl/control-S2 rl/control-S2b [--workers 16]
-> model/results/idiom/dev_outputs/<run>.pkl  {regime: {key: {"notes": [(part, onset, dur, pitch)], "insts": [...]}}}
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import pickle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "model" / "results" / "idiom" / "dev_outputs"
REGIMES = ("trio", "duo")
_W = {}


def _init(ckpt):
    import torch
    torch.set_num_threads(1)
    from model.grpo import load_split
    from model.net import Arranger
    ck = torch.load(ckpt, map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).eval()
    net.load_state_dict(ck["model"])
    _W.update(net=net, val={m.key: m for m in load_split("val")})


def _job(job):
    key, regime = job
    import model.augment as A
    from arrangement.instruments import load_ensemble
    from model.decode import decode_movement
    m = _W["val"][key]
    ens = load_ensemble(regime)
    insts = [i.key for i in ens.instruments]
    inotes, com = decode_movement(_W["net"], "cpu", m.src, insts, ens, True, m.tpq, True)
    return regime, key, {"notes": A.expand(inotes), "insts": insts, "interventions": com.n_intervened}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    from model.grpo import _val_keys
    keys = sorted(_val_keys())
    OUTD.mkdir(parents=True, exist_ok=True)
    for run in a.runs:
        ck = ROOT / "model" / "results" / run / "checkpoint.pt"
        with mp.get_context("fork").Pool(a.workers, initializer=_init, initargs=(str(ck),)) as pool:
            res = pool.map(_job, [(k, r) for r in REGIMES for k in keys], chunksize=1)
        out = {r: {} for r in REGIMES}
        for r, k, d in res:
            out[r][k] = d
        pickle.dump(out, open(OUTD / f"{run.replace('/', '_')}.pkl", "wb"))
        print(run, {r: len(v) for r, v in out.items()}, flush=True)


if __name__ == "__main__":
    main()
