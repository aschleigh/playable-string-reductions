"""Block 4 compute estimate: wall time of the network vs the checker in one masked decode.

    python -m model.profile_decode --regime trio --n 5

Read-only measurement. Times every forward pass (CUDA-synchronised) and every
GrowingChecker add/uncommit, and counts checker calls per input note.
"""
from __future__ import annotations

import argparse
import json
import time

import torch

import model.diagnose as D
from arrangement.instruments import load_ensemble
from model.net import Arranger


class Timed(torch.nn.Module):
    def __init__(self, net):
        super().__init__()
        self.net, self.t, self.calls = net, 0.0, 0

    def forward(self, b):
        torch.cuda.synchronize()
        t = time.perf_counter()
        out = self.net(b)
        torch.cuda.synchronize()
        self.t += time.perf_counter() - t
        self.calls += 1
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regime", default="trio")
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    ck = torch.load(D.RUN / "checkpoint.pt", map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).cuda().eval()
    net.load_state_dict(ck["model"])
    tn = Timed(net)
    ens = load_ensemble(a.regime)
    insts = [i.key for i in ens.instruments]
    from arrangement.decode.growing import GrowingChecker
    stats = {"add_t": 0.0, "add_n": 0, "unc_t": 0.0, "unc_n": 0}
    orig_add, orig_unc = GrowingChecker.add, GrowingChecker.uncommit

    def add(self, *x, **k):
        t = time.perf_counter(); r = orig_add(self, *x, **k)
        stats["add_t"] += time.perf_counter() - t; stats["add_n"] += 1
        return r

    def unc(self, *x, **k):
        t = time.perf_counter(); r = orig_unc(self, *x, **k)
        stats["unc_t"] += time.perf_counter() - t; stats["unc_n"] += 1
        return r
    GrowingChecker.add, GrowingChecker.uncommit = add, unc
    base = D.base_records(a.regime)[:: max(1, 150 // a.n)][: a.n]
    n_notes, t0 = 0, time.perf_counter()
    for r in base:
        src = D.sorted_source(r)
        n_notes += len(src)
        D.decode_instrumented(tn, "cuda", src, insts, ens, D.tpq_of(r))
    wall = time.perf_counter() - t0
    res = {"regime": a.regime, "movements": len(base), "input_notes": n_notes, "wall_s": wall,
           "net_s": tn.t, "net_calls": tn.calls, "checker_s": stats["add_t"] + stats["unc_t"],
           "checker_add_calls": stats["add_n"], "checker_add_calls_per_note": stats["add_n"] / n_notes,
           "us_per_checker_add": 1e6 * stats["add_t"] / max(1, stats["add_n"]),
           "other_s": wall - tn.t - stats["add_t"] - stats["unc_t"]}
    print(json.dumps(res, indent=1))
    (D.OUT / f"profile__{a.regime}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
