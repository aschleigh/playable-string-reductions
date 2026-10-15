"""Train the arranger: phase one (supervised recovery) and phase two (iterative,
partially committed states) as one run with a curriculum over the reveal fraction.

    python -m model.train --config model/config.yaml

Phase one (step < phase1_steps): only context-region notes (the previous 8
quarters, already decided at inference) are revealed. Phase two: in addition a
fraction r ~ U(0, reveal_max) of the window's notes is revealed, reveal_max
ramping linearly to its final value. Loss = CE(part) + CE(octave) + CE(realisation),
equal weights, unweighted classes, over unrevealed notes only.

Logs to Weights & Biases (offline mode unless WANDB_API_KEY is set; sync later
with `wandb sync model/wandb/offline-run-*`) and to model/results/<run>/log.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn
import yaml
from torch.utils.data import DataLoader, IterableDataset

import model.augment as A
from model.features import IGNORE, collate, encode
from model.label_stats import load_movements
from model.net import N_REAL, Arranger

ROOT = Path(__file__).resolve().parents[1]


def sample_example(mvs, rng, ranges, reveal_frac: float, augment=True, ensemble=None):
    mv = rng.choice(mvs)
    end = max(o for _, o, _, _ in mv)
    start = F(rng.randrange(0, max(1, int(end) - 4)))
    ens, inotes, _ = A.make_example(mv, start, rng, ranges, ensemble=ensemble, augment=augment)
    reveal = None
    if reveal_frac > 0:
        reveal = np.array([rng.random() < reveal_frac for _ in inotes], bool)
    return encode(inotes, A.ENSEMBLES[ens][0], start, reveal)


class Stream(IterableDataset):
    def __init__(self, split, cfg, step_ref):
        self.split, self.cfg, self.step_ref = split, cfg, step_ref

    def __iter__(self):
        info = torch.utils.data.get_worker_info()
        seed = self.cfg["seed"] * 1000 + (info.id if info else 0) + int(time.time())
        rng = random.Random(seed)
        mvs = load_movements(self.split)
        ranges = A.load_ranges()
        while True:
            step = self.step_ref.value
            r = 0.0
            if step >= self.cfg["phase1_steps"]:
                ramp = min(1.0, (step - self.cfg["phase1_steps"]) / max(1, self.cfg["ramp_steps"]))
                r = rng.random() * self.cfg["reveal_max"] * ramp
            yield sample_example(mvs, rng, ranges, r)


def losses(out, b, real_w=None):
    """real_w: optional class weights for the realisation CE (arranger-v2); validation stays unweighted."""
    lp = Fn.cross_entropy(out["part"].flatten(0, 1), b["y_part"].flatten(), ignore_index=IGNORE)
    lo = Fn.cross_entropy(out["octave"].flatten(0, 1), b["y_oct"].flatten(), ignore_index=IGNORE)
    lr = Fn.cross_entropy(out["real"].flatten(0, 1), b["y_real"].flatten(), ignore_index=IGNORE, weight=real_w)
    return lp, lo, lr


@torch.no_grad()
def evaluate(net, val_batches, device) -> dict:
    net.eval()
    agg = {"n": 0, "part": 0, "oct": 0, "real": 0, "loss": 0.0, "pred_nonplain": 0, "true_nonplain": 0}
    rec = np.zeros((N_REAL, 2))   # per realisation class: [correct, total]
    for b in val_batches:
        b = {k: v.to(device) for k, v in b.items()}
        out = net(b)
        lp, lo, lr = losses(out, b)
        m = b["y_part"] != IGNORE
        k = int(m.sum())
        agg["n"] += k
        agg["loss"] += float(lp + lo + lr) * k
        agg["part"] += int((out["part"].argmax(-1) == b["y_part"])[m].sum())
        agg["oct"] += int((out["octave"].argmax(-1) == b["y_oct"])[m].sum())
        pr = out["real"].argmax(-1)
        agg["real"] += int((pr == b["y_real"])[m].sum())
        agg["pred_nonplain"] += int((pr != 0)[m].sum())
        agg["true_nonplain"] += int((b["y_real"] != 0)[m].sum())
        for c in range(N_REAL):
            t = m & (b["y_real"] == c)
            rec[c, 1] += int(t.sum())
            rec[c, 0] += int((pr == c)[t].sum())
    net.train()
    n = max(1, agg["n"])
    res = {"val/loss": agg["loss"] / n, "val/acc_part": agg["part"] / n, "val/acc_octave": agg["oct"] / n,
           "val/acc_real": agg["real"] / n, "val/frac_pred_nonplain": agg["pred_nonplain"] / n,
           "val/frac_true_nonplain": agg["true_nonplain"] / n}
    for c, name in enumerate(A.REAL_NAMES):
        res[f"val/recall_{name}"] = rec[c, 0] / rec[c, 1] if rec[c, 1] else float("nan")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "model" / "config.yaml"))
    ap.add_argument("--steps", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(open(a.config))
    if a.steps:
        cfg["steps"] = a.steps
    torch.manual_seed(cfg["seed"])
    run = cfg["run_name"]
    out_dir = ROOT / "model" / "results" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = Arranger(**cfg["net"]).to(device)
    real_w = (torch.tensor(cfg["real_class_weights"], dtype=torch.float32, device=device)
              if cfg.get("real_class_weights") else None)
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.AdamW(net.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / cfg["warmup"])
                                              * 0.5 * (1 + np.cos(np.pi * min(1.0, s / cfg["steps"]))))
    import multiprocessing as mp
    step_ref = mp.Value("i", 0)
    dl = DataLoader(Stream("train", cfg, step_ref), batch_size=cfg["batch"], num_workers=cfg["workers"],
                    collate_fn=collate, persistent_workers=True, prefetch_factor=4)
    # fixed validation set: phase-one windows (r = 0) and phase-two windows (r = 0.5)
    vr = random.Random(12345)
    vm, ranges = load_movements("val"), A.load_ranges()
    val0 = [collate([sample_example(vm, vr, ranges, 0.0) for _ in range(cfg["batch"])]) for _ in range(cfg["val_batches"])]
    val5 = [collate([sample_example(vm, vr, ranges, 0.5) for _ in range(cfg["batch"])]) for _ in range(cfg["val_batches"])]
    os.environ.setdefault("WANDB_MODE", "online" if os.environ.get("WANDB_API_KEY") else "offline")
    os.environ.setdefault("WANDB_DIR", str(ROOT / "model"))
    import wandb
    wb = wandb.init(project="playable-arrangement", name=run, config={**cfg, "n_params": n_params})
    log_f = open(out_dir / "log.csv", "w", newline="")
    log_w = None
    (out_dir / "config.json").write_text(json.dumps({**cfg, "n_params": n_params}, indent=1))
    t0 = time.time()
    it = iter(dl)
    for step in range(cfg["steps"]):
        step_ref.value = step
        b = {k: v.to(device) for k, v in next(it).items()}
        out = net(b)
        lp, lo, lr = losses(out, b, real_w)
        loss = lp + lo + lr
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step(); sched.step()
        if step % cfg["log_every"] == 0 or step == cfg["steps"] - 1:
            m = b["y_real"] != IGNORE
            row = {"step": step, "phase": 1 if step < cfg["phase1_steps"] else 2, "lr": sched.get_last_lr()[0],
                   "train/loss": float(loss), "train/loss_part": float(lp), "train/loss_octave": float(lo),
                   "train/loss_real": float(lr),
                   "train/frac_pred_nonplain": float((out["real"].argmax(-1) != 0)[m].float().mean()),
                   "elapsed_s": time.time() - t0}
            if step % cfg["val_every"] == 0 or step == cfg["steps"] - 1:
                row.update({k.replace("val/", "val_r0/"): v for k, v in evaluate(net, val0, device).items()})
                row.update({k.replace("val/", "val_r50/"): v for k, v in evaluate(net, val5, device).items()})
                torch.save({"model": net.state_dict(), "cfg": cfg, "step": step}, out_dir / "checkpoint.pt")
            wb.log(row, step=step)
            if log_w is None:
                cols = list(row.keys()) + [f"{p}/{x}" for p in ("val_r0", "val_r50") for x in
                        ["loss", "acc_part", "acc_octave", "acc_real", "frac_pred_nonplain", "frac_true_nonplain"]
                        + [f"recall_{n}" for n in A.REAL_NAMES]]
                log_w = csv.DictWriter(log_f, fieldnames=list(dict.fromkeys(cols)), extrasaction="ignore")
                log_w.writeheader()
            log_w.writerow(row); log_f.flush()
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    torch.save({"model": net.state_dict(), "cfg": cfg, "step": cfg["steps"]}, out_dir / "checkpoint.pt")
    wb.finish()


if __name__ == "__main__":
    main()
