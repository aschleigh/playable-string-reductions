"""Dev-split validation of a saved GRPO checkpoint: the same validate() and dev movements as training.

    python -m model.val_checkpoint --run rl-SM2Z [--n-val 20] [--workers 16]
Writes model/results/rl/<run>/final_val.json.
"""
import argparse
import json
import multiprocessing as mp
from pathlib import Path

import torch

import model.grpo as G


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--n-val", type=int, default=20)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    rd = G.RL / a.run
    ck = torch.load(rd / "checkpoint.pt", map_location="cpu")
    w = Path("/dev/shm") / f"val_{a.run}.pt"
    torch.save(ck["model"], w)
    cfg = json.loads((rd / "config.json").read_text())
    base_ck = cfg["base_checkpoint"]
    with mp.get_context("fork").Pool(a.workers, initializer=G._worker_init,
                                     initargs=(base_ck, cfg.get("ctx_run") or cfg["base"], cfg["setting"])) as pool:
        res = G.validate(pool, G.REGIMES, str(w), 1, a.n_val)
    w.unlink()
    res["step"] = ck["step"]
    (rd / "final_val.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
