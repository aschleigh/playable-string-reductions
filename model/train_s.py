"""Control S (BLOCK4.md 2g): arranger-v2b fine-tuned SUPERVISED on feasible targets, i.e. the
oracle-under-mask labels (true option first, then the model's ranked options, under the checker-v4
mask) of the train split, from `model.grpo contexts`. Same windows, curriculum (reveal r ~ U(0, 0.9))
and realisation class weights as v2b; no RL. If S matches RL, the constraint can be internalised
without RL.

    python -m model.train_s --run-name control-S [--steps 3000]
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch

import model.augment as A
from model.features import IGNORE, collate, encode
from model.grpo import RL, REGIMES, load_split, windows
from model.net import Arranger
from model.train import losses

ROOT = Path(__file__).resolve().parents[1]


def load_oracle(run="arranger-v2b"):
    lab = {}
    for p in sorted((RL / "contexts").glob(f"{run}__train.*.pkl")):
        for k, d in pickle.load(open(p, "rb")).items():
            lab[k] = d["oracle"]
    return lab


def example(m, labels, regime, w0, rng, reveal_max):
    lo, hi = w0 - A.CONTEXT, w0 + A.WINDOW
    ids = [i for i, n in enumerate(m.src) if lo <= n[1] < hi]
    inotes = []
    for i in ids:
        p, o, d, x = m.src[i]
        pt, oc, re = labels[i]
        inotes.append(A.INote(o, d, x, part=pt, octave=oc, real=re, context=o < w0, src=p))
    r = rng.random() * reveal_max
    reveal = np.array([rng.random() < r for _ in inotes], bool)
    return encode(inotes, A.ENSEMBLES[regime][0], w0, reveal)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", default="control-S")
    ap.add_argument("--base", default="arranger-v2b")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ctx-run", default=None)
    ap.add_argument("--targets", default="oracle", choices=["oracle", "s2"], help="oracle-under-mask (control S) or S2 (R44)")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    torch.manual_seed(a.seed)
    ck = torch.load(ROOT / "model" / "results" / a.base / "checkpoint.pt", map_location="cpu")
    cfg = ck["cfg"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = Arranger(**cfg["net"]).to(device)
    net.load_state_dict(ck["model"])
    real_w = torch.tensor(cfg["real_class_weights"], device=device) if cfg.get("real_class_weights") else None
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    if a.targets == "s2":   # R44: S2 targets (model/targets_s2.py), {key: {regime: labels}}
        lab = pickle.load(open(RL / "targets_s2__train.pkl", "rb"))
    else:
        lab = load_oracle(a.ctx_run or a.base)
    mvs = [m for m in load_split("train") if m.key in lab]
    jobs = [(m, r, w0) for m in mvs for r in REGIMES if r in lab[m.key] for w0 in windows(m, 384)]
    od = RL / a.run_name
    od.mkdir(parents=True, exist_ok=True)
    (od / "config.json").write_text(json.dumps({**vars(a), "n_windows": len(jobs), "base_step": ck["step"]}, indent=1))
    os.environ.setdefault("WANDB_MODE", "online" if os.environ.get("WANDB_API_KEY") else "offline")
    os.environ.setdefault("WANDB_DIR", str(ROOT / "model"))
    import wandb
    wb = wandb.init(project="playable-arrangement", name=a.run_name, config=vars(a), mode=os.environ["WANDB_MODE"])
    log = open(od / "log.csv", "w")
    log.write("step,loss,loss_part,loss_octave,loss_real,elapsed_s\n")
    t0 = time.time()
    for step in range(a.steps):
        batch = [example(m, lab[m.key][r], r, w0, rng, 0.9) for m, r, w0 in rng.sample(jobs, a.batch)]
        b = {k: v.to(device) for k, v in collate(batch).items()}
        lp, lo, lr_ = losses(net(b), b, real_w)
        loss = lp + lo + lr_
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if step % 50 == 0 or step == a.steps - 1:
            row = {"loss": float(loss), "loss_part": float(lp), "loss_octave": float(lo), "loss_real": float(lr_)}
            wb.log(row, step=step)
            log.write(f"{step},{row['loss']},{row['loss_part']},{row['loss_octave']},{row['loss_real']},{time.time() - t0}\n"); log.flush()
            print(json.dumps({"step": step, **{k: round(v, 4) for k, v in row.items()}}), flush=True)
    torch.save({"model": net.state_dict(), "cfg": {**cfg, "run_name": a.run_name}, "step": a.steps, "control_s": vars(a)},
               od / "checkpoint.pt")
    wb.finish()


if __name__ == "__main__":
    main()
