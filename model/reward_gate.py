"""Reward gate for R8 (BLOCK7 Step 2, merged with Amendment A; R79), on the dev split only, before any RL run.

    python -m model.reward_gate [--regimes trio duo solo_flute piano] [--workers 16]
-> model/results/rl/reward_gate.json, reward_gate.md

Per regime: the base system (strings control-S2c, flute / piano control-FK2) is decoded masked, melody-first on the 61
dev movements; every 16-quarter window is scored with each R8 setting of the regime, as the RL engine scores a rollout.
Hacks are built from the base's own labels, so they differ from it only in the hacked respect:
  restrike8   every kept note re-struck as 8ths (REPEAT; the rl-C / rl-AZ2 hack)
  melody_only everything but the top tier dropped (strings, piano)
  zigzag      every other kept melody note moved an octave (relocation credit without a line)
  inner_dump  every kept inner note moved two octaves (strings, piano)
  keep_all    every note in its true part, plain, no mask (strings: no reduction, double-stop heavy)
  cut_all     every kept note CUT (flute: breaths for free)
  drop_half   every other melody note dropped (flute)
Pass rule (fixed in BLOCK7 Step 2; R81: over the windows the hack changes): for every hack, the share of those windows
where the base outscores it (ties half) >= 0.90.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fractions import Fraction as Fr

import model.augment as A
import model.grpo as G

ROOT = Path(__file__).resolve().parents[1]
BASE = {"trio": "rl/control-S2c", "duo": "rl/control-S2c", "solo_flute": "rl/control-FK2", "piano": "rl/control-FK2"}
SETS = {"trio": ["R8S2", "R8S4"], "duo": ["R8S2", "R8S4"], "solo_flute": ["R8F05", "R8F10"], "piano": ["R8K"]}
HACKS = {"trio": ["restrike8", "melody_only", "zigzag", "inner_dump", "keep_all"],
         "duo": ["restrike8", "melody_only", "zigzag", "inner_dump", "keep_all"],
         "solo_flute": ["restrike8", "zigzag", "cut_all", "drop_half"],
         "piano": ["restrike8", "melody_only", "zigzag", "inner_dump"]}
ENS = {"trio": "trio", "duo": "duo", "solo_flute": "solo_flute", "piano": "piano"}
_W = {}


def _init(regime):
    import torch
    torch.set_num_threads(1)
    from model.net import Arranger
    ck = torch.load(ROOT / "model" / "results" / BASE[regime] / "checkpoint.pt", map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).eval()
    net.load_state_dict(ck["model"])
    G.configure(ck["cfg"]["net"].get("n_real", 5))
    _W.update(net=net, val={m.key: m for m in G.load_split("val")})


def hack(m, regime, labels, name):
    """labels: [(part, octave, real)] in m.src order. Returns hacked labels."""
    out = []
    tops = [i for i in sorted(range(len(m.src)), key=lambda i: m.src[i][1]) if m.tiers[i] == "top" and labels[i][0] != A.DROP]
    alt = set(tops[1::2])
    true_part = {"trio": {0: 0, 1: 0, 2: 1, 3: 2}, "duo": {0: 0, 1: 0, 2: 1, 3: 1}}
    for i, (p, oc, re) in enumerate(labels):
        t = m.tiers[i]
        if name == "keep_all":
            out.append((true_part[regime][m.src[i][0]], 0, A.PLAIN))
        elif p == A.DROP:
            out.append((p, oc, re))
        elif name == "restrike8":
            out.append((p, oc, A.REPEAT))
        elif name == "melody_only":
            out.append((p, oc, re) if t == "top" else (A.DROP, 0, A.PLAIN))
        elif name == "zigzag":
            out.append((p, (oc + 12 if oc + 12 <= 24 else oc - 12) if i in alt else oc, re))
        elif name == "inner_dump":
            out.append((p, (oc + 24 if oc <= 0 else oc - 24) if t == "inner" else oc, re))
        elif name == "cut_all":
            out.append((p, oc, A.CUT))
        elif name == "drop_half":
            out.append((A.DROP, 0, A.PLAIN) if i in alt else (p, oc, re))
    return out


def changed(m, labels, other):
    """R81: per window (as score), whether `other` differs from `labels` in it (the hack touches the window)."""
    end = max(o + d for _, o, d, _ in m.src)
    out, w0 = [], Fr(0)
    while w0 < end:
        win = [k for k, n in enumerate(m.src) if w0 <= n[1] < w0 + A.WINDOW]
        if win:
            out.append(any(labels[k] != other[k] for k in win))
        w0 += A.WINDOW
    return out


def score(m, regime, labels, setting):
    """Mean R8 over the movement's 16-quarter windows, as the RL engine scores a rollout (context notes from before w0)."""
    inotes = [A.INote(o, d, x, part=p, octave=oc, real=re, src=sp, cut_end=m.cut[i][0], cut_kind=m.cut[i][1])
              for i, ((sp, o, d, x), (p, oc, re)) in enumerate(zip(m.src, labels))]
    end = max(o + d for _, o, d, _ in m.src)
    rs, w0 = [], Fr(0)
    while w0 < end:
        win = [k for k, n in enumerate(inotes) if w0 <= n.onset < w0 + A.WINDOW]
        if win:
            ctx = [n for n in inotes if w0 - A.CONTEXT <= n.onset < w0]
            tr = SimpleNamespace(out_notes=A.expand([inotes[k] for k in win]), parts={"_ctx_notes": A.expand(ctx)},
                                 labels=[(inotes[k].part, inotes[k].octave, inotes[k].real) for k in win],
                                 intervened=np.zeros(0, bool))
            rs.append(G.window_reward(m, regime, w0, tr, setting)["R"])
        w0 += A.WINDOW
    return rs


def _job(job):
    key, regime = job
    from arrangement.instruments import load_ensemble
    from model.decode import decode_movement
    m = _W["val"][key]
    ens = load_ensemble(ENS[regime])
    inotes, _ = decode_movement(_W["net"], "cpu", m.src, [i.key for i in ens.instruments], ens, True, m.tpq, True)
    # decode_movement sorts by (onset, pitch, dur), as m.src is sorted: labels align with m.src
    labels = [(n.part, n.octave, n.real) for n in inotes]
    out = {}
    for sname in SETS[regime]:
        st = G.SETTINGS[sname]
        out[sname] = {"base": score(m, regime, labels, st)}
        for h in HACKS[regime]:
            hl = hack(m, regime, labels, h)
            out[sname][h] = score(m, regime, hl, st)
            out[sname][h + "__changed"] = changed(m, labels, hl)
    return key, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", nargs="+", default=list(SETS))
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    keys = sorted(G._val_keys())
    res, ok_all, md = {}, True, ["| regime | setting | hack | base mean R | hack mean R | share base > hack | ties | changed windows | pass |", "|---|---|---|---|---|---|---|---|---|"]
    for regime in a.regimes:
        with mp.get_context("fork").Pool(a.workers, initializer=_init, initargs=(regime,)) as pool:
            rows = pool.map(_job, [(k, regime) for k in keys], chunksize=1)
        res[regime] = {}
        for sname in SETS[regime]:
            base = np.concatenate([r[sname]["base"] for _, r in rows])
            res[regime][sname] = {"base_mean": float(base.mean())}
            for h in HACKS[regime]:
                hv = np.concatenate([r[sname][h] for _, r in rows])
                c = np.concatenate([r[sname][h + "__changed"] for _, r in rows]).astype(bool)   # R81: changed windows only
                base_c, hv_c = base[c], hv[c]
                share = float(((base_c > hv_c) + 0.5 * (base_c == hv_c)).mean()) if c.any() else 1.0
                ok = share >= 0.90
                ok_all &= ok
                res[regime][sname][h] = {"mean": float(hv.mean()), "share_base_wins": share, "ties": float((base_c == hv_c).mean()),
                                            "hack_wins": float((hv_c > base_c).mean()), "n_changed": int(c.sum()),
                                            "n_windows": len(c), "pass": ok}
                md.append(f"| {regime} | {sname} | {h} | {base.mean():.3f} | {hv.mean():.3f} | {share:.3f} | {(base_c == hv_c).mean():.3f} | {c.sum()}/{len(c)} | {'yes' if ok else 'NO'} |")
        print("\n".join(l for l in md if f"| {regime} |" in l), flush=True)
    res["PASS"] = ok_all
    out = ROOT / "model" / "results" / "rl"
    (out / "reward_gate.json").write_text(json.dumps(res, indent=1))
    (out / "reward_gate.md").write_text("\n".join(md) + f"\n\n**Gate: {'PASS' if ok_all else 'FAIL'}**\n")
    print(f"Gate: {'PASS' if ok_all else 'FAIL'}")


if __name__ == "__main__":
    main()
