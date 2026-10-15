"""Double-stop usage per output part vs real quartet parts (R44). Dev split, masked greedy decode.

    python -m model.double_stop_stats --runs arranger-v2b rl/control-S rl/control-S2 [--melody-first]
"""
import argparse
import json
import multiprocessing as mp
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import torch

import model.augment as A
import model.grpo as G
from arrangement.instruments import load_ensemble
from model.decode import decode_movement
from model.net import Arranger

ROOT = Path(__file__).resolve().parents[1]


def ds_moments(notes):
    ns = sorted(n for n in notes if n[1] > 0)
    out, active, k = [], [], 0
    for t in sorted({n[0] for n in ns}):
        while k < len(ns) and ns[k][0] <= t:
            active.append(ns[k]); k += 1
        active = [n for n in active if n[0] + n[1] > t]
        if len(active) >= 2:
            out.append(t)
    return out


def stats(parts):
    n_notes = n_ds = q8 = 0
    for ns in parts:
        n_notes += len(ns)
        m = ds_moments(ns)
        n_ds += len(m)
        q8 += sum(b - a <= F(1, 2) for a, b in zip(m, m[1:]))
    return {"ds_per_100_notes": 100 * n_ds / max(1, n_notes), "next_ds_within_8th": q8 / max(1, n_ds)}


def real():
    by = defaultdict(list)
    for line in open(ROOT / "model" / "data" / "train.jsonl"):
        d = json.loads(line)
        parts = defaultdict(list)
        for p, o, du, x in d["notes"]:
            parts[int(p)].append((F(o), F(du), int(x)))
        for p, ns in parts.items():
            by[["Vn1", "Vn2", "Va", "Vc"][p]].append(ns)
    return {k: stats(v) for k, v in by.items()}


_net = {}


def _job(args):
    run, mf, regime, m = args
    if run not in _net:
        torch.set_num_threads(1)
        ck = torch.load(ROOT / "model" / "results" / run / "checkpoint.pt", map_location="cpu")
        net = Arranger(**ck["cfg"]["net"]).eval()
        net.load_state_dict(ck["model"])
        _net[run] = net
    ens = load_ensemble(regime)
    inotes, com = decode_movement(_net[run], "cpu", m.src, [i.key for i in ens.instruments], ens, True, m.tpq, mf)
    by = defaultdict(list)
    for p, o, d, x in A.expand(inotes):
        by[p].append((o, d, x))
    return dict(by), sum(n.part == A.DROP for n in inotes), len(inotes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--melody-first", action="store_true")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    out = {"real": real()}
    print("real", {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in out["real"].items()}, flush=True)
    mvs = G.load_split("val")
    with mp.get_context("fork").Pool(a.workers) as pool:
        for run in a.runs:
            for regime in ("trio", "duo"):
                res = pool.map(_job, [(run, a.melody_first, regime, m) for m in mvs], chunksize=1)
                names = [i.key for i in load_ensemble(regime).instruments]
                row = {nm: stats([r[0].get(p, []) for r in res]) for p, nm in enumerate(names)}
                row["drop_rate"] = sum(r[1] for r in res) / sum(r[2] for r in res)
                out[f"{run} | {regime}"] = row
                print(run, regime, {k: ({kk: round(vv, 3) for kk, vv in v.items()} if isinstance(v, dict) else round(v, 3))
                                    for k, v in row.items()}, flush=True)
    (G.RL / f"double_stop_stats{'_mf' if a.melody_first else ''}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
