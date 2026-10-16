"""The idiomatic part model P (BLOCK5.md Step 2): a small causal transformer over the events of one string part,
trained on the real parts of the train quartets. Scores how much an output part looks like a real part.

    python -m model.idiom train      [--steps 6000]                 -> model/results/idiom/P/checkpoint.pt
    python -m model.idiom calibrate                                  -> model/results/idiom/P/calib.json

Events: one per onset in the part (notes starting together are one event). Eight features, each its own
softmax head: interval from the previous event's top note, register, duration, rest before, voices
sounding, double-stop interval, re-strike of a still-sounding pitch, and sub-beat position.
Deviation from the brief (R52): the sub-beat position (onset within the quarter) replaces the metre
position, because model outputs carry no time signature.

Score: per-event log-likelihood (summed over heads), averaged over windows of WIN events; a part's z is the
mean over its windows of (window mean - mu_inst) / sd_inst, mu and sd from the real dev parts' windows.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model" / "results" / "idiom" / "P"
INSTS = ("violin", "viola", "cello")
LOW = {"violin": 55, "viola": 48, "cello": 36}
SRC_INST = {0: "violin", 1: "violin", 2: "viola", 3: "cello"}
HEADS = {"interval": 50, "register": 20, "dur": 14, "rest": 6, "voices": 3, "dsint": 14, "restrike": 2, "beat": 5}
CTX = 256
WIN = 64


# ------------------------------------------------------------ events

def _beat(o: F) -> int:
    f = o - math.floor(o)
    if f == 0:
        return 0
    if f == F(1, 2):
        return 1
    if f in (F(1, 4), F(3, 4)):
        return 2
    if f in (F(1, 3), F(2, 3)):
        return 3
    return 4


def _dur(d: F) -> int:
    return int(min(13, max(0, round(2 * math.log2(float(d) * 8)))))


def _rest(g: F) -> int:
    if g <= 0:
        return 0
    for k, b in enumerate((F(1, 4), F(1, 2), F(1), F(2)), 1):
        if g <= b:
            return k
    return 5


def part_events(notes, inst: str, return_onsets: bool = False):
    """notes: [(onset, dur, pitch)] of one part (Fractions or numbers). -> int array [T, 8] in HEADS order
    (and the event onsets, when return_onsets)."""
    ns = sorted((F(o), F(d), int(x)) for o, d, x in notes if F(d) > 0)
    by = {}
    for o, d, x in ns:
        by.setdefault(o, []).append((d, x))
    ev = []
    active = []                    # (end, pitch) sounding from earlier onsets
    prev_top, last_end = None, None
    for o in sorted(by):
        active = [(e, x) for e, x in active if e > o]
        start = by[o]
        top = max(x for _, x in start)
        held = {x for _, x in active}
        sounding = sorted({x for _, x in start} | held, reverse=True)
        nv = len(sounding)
        dsint = 0 if nv < 2 else min(13, max(1, sounding[0] - sounding[1]))
        iv = 49 if prev_top is None else min(24, max(-24, top - prev_top)) + 24
        reg = min(19, max(0, (top - LOW[inst]) // 3))
        rest = 0 if last_end is None or active else _rest(o - last_end)
        ev.append((iv, reg, _dur(max(d for d, _ in start)), rest, min(nv, 3) - 1, dsint,
                   int(any(x in held for _, x in start)), _beat(o)))
        for d, x in start:
            active.append((o + d, x))
        prev_top = top
        last_end = max([e for e, _ in active] + [last_end or o])
    arr = np.array(ev, dtype=np.int64).reshape(-1, len(HEADS))
    return (arr, sorted(by)) if return_onsets else arr


def real_parts(split: str):
    """[(key, source part, inst, events)] for the real parts of a split."""
    out = []
    for line in open(ROOT / "model" / "data" / f"{split}.jsonl"):
        d = json.loads(line)
        parts = {}
        for p, o, du, x in d["notes"]:
            parts.setdefault(int(p), []).append((F(o), F(du), int(x)))
        for p, ns in sorted(parts.items()):
            out.append((d["key"], p, SRC_INST[p], part_events(ns, SRC_INST[p])))
    return out


# ------------------------------------------------------------ model

class PartLM(nn.Module):
    def __init__(self, d=256, layers=4, heads=4, ctx=CTX + 1):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(n, d) for n in HEADS.values()])
        self.inst = nn.Embedding(len(INSTS), d)
        self.pos = nn.Embedding(ctx, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True, norm_first=True)
        self.tr = nn.TransformerEncoder(layer, layers)
        self.norm = nn.LayerNorm(d)
        self.out = nn.ModuleList([nn.Linear(d, n) for n in HEADS.values()])

    def forward(self, ev, inst):
        """ev [B, T, 8], inst [B] -> list of logits [B, T, n_h] predicting ev[:, t] from inst + ev[:, :t]."""
        B, T, _ = ev.shape
        x = sum(e(ev[..., k]) for k, e in enumerate(self.emb))           # [B, T, d]
        x = torch.cat([self.inst(inst)[:, None], x[:, :-1]], 1)          # shift right; position 0 = instrument
        x = x + self.pos(torch.arange(T, device=ev.device))[None]
        mask = torch.triu(torch.ones(T, T, dtype=torch.bool, device=ev.device), 1)
        h = self.norm(self.tr(x, mask=mask, is_causal=True))
        return [o(h) for o in self.out]


def event_ll(logits, ev) -> torch.Tensor:
    """Summed per-event log-likelihood over heads, [B, T]."""
    return sum(torch.log_softmax(lg, -1).gather(-1, ev[..., k:k + 1])[..., 0] for k, lg in enumerate(logits))


@torch.no_grad()
def score_events(net, ev: np.ndarray, inst: str, device) -> np.ndarray:
    """Per-event log-likelihood of a whole part. Chunks of CTX events; after the first chunk, each chunk
    re-reads the previous CTX // 4 events as context, which are not scored again."""
    T = len(ev)
    if T == 0:
        return np.zeros(0)
    ll = np.zeros(T)
    ov = CTX // 4
    s = 0
    while s < T:
        a = max(0, s - ov) if s else 0
        b = min(T, a + CTX)
        x = torch.from_numpy(ev[a:b])[None].to(device)
        lls = event_ll(net(x, torch.tensor([INSTS.index(inst)], device=device)), x)[0].cpu().numpy()
        ll[s:b] = lls[s - a:]
        s = b
    return ll


def window_means(ll: np.ndarray) -> np.ndarray:
    if len(ll) == 0:
        return np.zeros(0)
    k = max(1, len(ll) // WIN)
    return np.array([w.mean() for w in np.array_split(ll, k)])


def load(device="cpu"):
    ck = torch.load(OUT / "checkpoint.pt", map_location=device)
    net = PartLM(**ck["cfg"]).to(device).eval()
    net.load_state_dict(ck["model"])
    calib = json.loads((OUT / "calib.json").read_text()) if (OUT / "calib.json").exists() else None
    return net, calib


def part_z(net, calib, notes, inst: str, device, duo_cello: bool = False) -> float:
    """z of one output part. duo_cello (R51 decision 2): scored as cello and as viola, the better taken."""
    def z(as_inst):
        wm = window_means(score_events(net, part_events(notes, as_inst), as_inst, device))
        if len(wm) == 0:
            return float("nan")
        c = calib[as_inst]
        return float(((wm - c["mu"]) / c["sd"]).mean())
    return max(z("cello"), z("viola")) if duo_cello else z(inst)


_RL = {}


def window_term(out_notes, insts, regime: str, w0, w1) -> tuple[float, float]:
    """RL reward term (BLOCK5.md Step 4): (term, mean z) for one rollout window. out_notes are the window's and
    its context's output notes; each part's events are scored with the context as P context, and only events
    starting in [w0, w1) count. term = clip(mean over parts of min(z, 0) / 3, -1, 0): penalty only."""
    if not _RL:
        torch.set_num_threads(1)
        _RL["net"], _RL["calib"] = load("cpu")
    net, calib = _RL["net"], _RL["calib"]
    zs = []
    for p, inst in enumerate(insts):
        ns = [(o, d, x) for q, o, d, x in out_notes if q == p]
        cands = ("cello", "viola") if (regime == "duo" and inst == "cello") else (inst,)
        best = None
        for as_inst in cands:
            ev, ons = part_events(ns, as_inst, return_onsets=True)
            sel = np.array([w0 <= o < w1 for o in ons], dtype=bool)
            if sel.sum() < 4:
                continue
            ll = score_events(net, ev, as_inst, "cpu")[sel].mean()
            z = (ll - calib[as_inst]["mu"]) / calib[as_inst]["sd"]
            best = z if best is None else max(best, z)
        if best is not None:
            zs.append(float(best))
    if not zs:
        return 0.0, float("nan")
    return float(np.clip(np.mean([min(z, 0.0) for z in zs]) / 3, -1, 0)), float(np.mean(zs))


def auc(hi, lo) -> float:
    """P(x > y) for x in hi, y in lo (ties count half), the Mann-Whitney AUC; NaNs ignored."""
    from scipy.stats import rankdata
    hi = np.asarray([h for h in hi if h == h], dtype=float)
    lo = np.asarray([l for l in lo if l == l], dtype=float)
    if len(hi) == 0 or len(lo) == 0:
        return float("nan")
    r = rankdata(np.concatenate([hi, lo]))
    return float((r[:len(hi)].sum() - len(hi) * (len(hi) + 1) / 2) / (len(hi) * len(lo)))


# ------------------------------------------------------------ commands

def cmd_train(a):
    rng = random.Random(a.seed)
    torch.manual_seed(a.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr = [(INSTS.index(i), ev) for _, _, i, ev in real_parts("train") if len(ev) > 8]
    va = [(INSTS.index(i), ev) for _, _, i, ev in real_parts("val") if len(ev) > 8]
    w = np.array([len(ev) for _, ev in tr], dtype=float)
    w /= w.sum()
    cfg = {"d": a.d, "layers": a.layers, "heads": 4}
    net = PartLM(**cfg).to(device)
    n_par = sum(p.numel() for p in net.parameters())
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / 200) * 0.5 * (1 + math.cos(math.pi * s / a.steps)))
    OUT.mkdir(parents=True, exist_ok=True)
    log = open(OUT / "log.csv", "w")
    log.write("step,train_ll,val_ll,elapsed_s\n")
    print(json.dumps({"params": n_par, "train_parts": len(tr), "val_parts": len(va),
                      "train_events": int(sum(len(e) for _, e in tr))}), flush=True)
    nrng = np.random.default_rng(a.seed)

    def batch(src, B):
        ids = nrng.choice(len(src), B, p=w) if src is tr else nrng.choice(len(src), B)
        evs, ins, lens = [], [], []
        for i in ids:
            inst, ev = src[i]
            s = rng.randrange(0, max(1, len(ev) - CTX + 1))
            e = ev[s:s + CTX]
            evs.append(np.pad(e, ((0, CTX - len(e)), (0, 0))))
            ins.append(inst)
            lens.append(len(e))
        x = torch.from_numpy(np.stack(evs)).to(device)
        m = (torch.arange(CTX)[None] < torch.tensor(lens)[:, None]).to(device)
        return x, torch.tensor(ins, device=device), m

    t0 = time.time()
    for step in range(a.steps):
        net.train()
        x, ins, m = batch(tr, a.batch)
        ll = event_ll(net(x, ins), x)
        loss = -(ll * m).sum() / m.sum()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        sched.step()
        if step % 250 == 0 or step == a.steps - 1:
            net.eval()
            with torch.no_grad():
                vs = []
                for _ in range(4):
                    xv, iv, mv = batch(va, a.batch)
                    lv = event_ll(net(xv, iv), xv)
                    vs.append(float((lv * mv).sum() / mv.sum()))
            log.write(f"{step},{-float(loss)},{np.mean(vs)},{time.time() - t0}\n"); log.flush()
            print(json.dumps({"step": step, "train_ll": round(-float(loss), 3), "val_ll": round(float(np.mean(vs)), 3)}), flush=True)
    torch.save({"model": net.state_dict(), "cfg": cfg, "step": a.steps, "args": vars(a), "params": n_par},
               OUT / "checkpoint.pt")


def cmd_calibrate(a):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net, _ = load(device)
    wins = {i: [] for i in INSTS}
    for _, _, inst, ev in real_parts("val"):
        wins[inst] += list(window_means(score_events(net, ev, inst, device)))
    calib = {i: {"mu": float(np.mean(v)), "sd": float(np.std(v)), "n_windows": len(v)} for i, v in wins.items()}
    (OUT / "calib.json").write_text(json.dumps(calib, indent=1))
    print(json.dumps(calib, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--steps", type=int, default=6000)
    t.add_argument("--batch", type=int, default=64)
    t.add_argument("--lr", type=float, default=3e-4)
    t.add_argument("--d", type=int, default=256)
    t.add_argument("--layers", type=int, default=4)
    t.add_argument("--seed", type=int, default=0)
    sub.add_parser("calibrate")
    a = ap.parse_args(argv)
    {"train": cmd_train, "calibrate": cmd_calibrate}[a.cmd](a)


if __name__ == "__main__":
    main()
