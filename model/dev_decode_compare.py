"""Compare decode v2 and v3 (melody-first, R42) on the dev split, for several checkpoints.

    python -m model.dev_decode_compare --runs arranger-v2b rl/control-S rl/rl-SM2Z [--n-val 61]
Same validate() metrics as GRPO training (masked greedy decode on dev movements). Writes
model/results/rl/dev_decode_compare.json.
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path

import torch

import model.grpo as G

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["arranger-v2b", "rl/control-S", "rl/rl-SM2Z"])
    ap.add_argument("--n-val", type=int, default=61)
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    out = {}
    base = str(ROOT / "model" / "results" / "arranger-v2b" / "checkpoint.pt")
    with mp.get_context("fork").Pool(a.workers, initializer=G._worker_init, initargs=(base, "arranger-v2b", "M2")) as pool:
        for v, run in enumerate(a.runs):
            ck = torch.load(ROOT / "model" / "results" / run / "checkpoint.pt", map_location="cpu")
            w = Path("/dev/shm") / f"cmp_{run.replace('/', '_')}.pt"
            torch.save(ck["model"], w)
            for mf in (False, True):
                res = G.validate(pool, G.REGIMES, str(w), 100 + 2 * v + mf, a.n_val, melody_first=mf)
                out[f"{run} | {'v3 melody-first' if mf else 'v2'}"] = res
                print(run, "v3" if mf else "v2", {k: round(x, 3) for k, x in res.items()
                                                    if any(s in k for s in ("fidelity_M", "top_retention_M", "retention_top",
                                                                            "intervention", "unneeded", "note_ratio", "drop"))}, flush=True)
            w.unlink()
    (G.RL / "dev_decode_compare.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
