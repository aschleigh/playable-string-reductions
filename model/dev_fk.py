"""Block 6 dev-split evaluation for solo flute and solo piano (BLOCK6.md Steps 4-5; dev only, R63).

    python -m model.dev_fk --runs rl/control-J [--workers 16] [--targets]
-> model/results/idiom/../block6/dev_fk__<run>.json and printed table

Masked greedy decode (model/decode.py, melody-first, checker-v6) of the 61 dev movements as solo_flute and piano.
Also, for reference: the F/K target rule applied to the dev movements (--targets) and, for flute, the "top line"
baseline (the top-tier note at each onset, folded into C4-C7, each note cut at the next onset so the line is
monophonic).
Metrics: melody retention (top tier: exact pitch, count; and reward-M style, duration-weighted with 0.8 credit an
octave or two away), bass retention, harmony (beat chroma cosine), note ratio, interventions, drops by tier;
flute: breaths (rests >= an eighth) per 32 quarters and the longest unbroken run; piano: kept share by tier.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model" / "results" / "block6"
ENS = {"flute": "solo_flute", "piano": "piano"}
_W = {}


def _init(ckpt):
    import torch
    torch.set_num_threads(1)
    from model.grpo import load_split
    _W["val"] = {m.key: m for m in load_split("val")}
    if ckpt:
        from model.net import Arranger
        ck = torch.load(ckpt, map_location="cpu")
        net = Arranger(**ck["cfg"]["net"]).eval()
        net.load_state_dict(ck["model"])
        _W["net"] = net


def harmony(out_notes, src):
    from model.grpo import chroma_per_beat
    end = max(o + d for _, o, d, _ in src)
    Cs, Co = chroma_per_beat(tuple(src), F(0), end), chroma_per_beat(tuple(out_notes), F(0), end)
    nb, na = np.linalg.norm(Cs, axis=1), np.linalg.norm(Co, axis=1)
    sel = nb > 0
    return float(np.where(na[sel] > 0, (Co[sel] * Cs[sel]).sum(1) / np.maximum(na[sel] * nb[sel], 1e-300), 0).mean())


def top_line(m):
    tops = sorted((m.src[i][1], m.src[i][2], m.src[i][3]) for i in range(len(m.src)) if m.tiers[i] == "top")
    out = []
    for k, (o, d, x) in enumerate(tops):
        while x < 60:
            x += 12
        while x > 96:
            x -= 12
        nxt = next((tops[j][0] for j in range(k + 1, len(tops)) if tops[j][0] > o), None)
        dd = min(d, nxt - o) if nxt is not None else d
        if out and out[-1][1] == o:      # same onset: keep the highest only
            continue
        out.append((0, o, dd, x))
    return out


def metrics(m, out_notes, regime, interventions=0, drops=None):
    from arrangement.eval.record import make_score
    from arrangement.eval.reduction import reduction_metrics
    from model.grpo import SETTINGS, kept_weights
    inst = "flute" if regime == "flute" else "piano"
    out = make_score([(inst.capitalize(), inst)], out_notes)
    src = make_score([("Violin 1", "violin"), ("Violin 2", "violin"), ("Viola", "viola"), ("Violoncello", "cello")], m.src)
    red = reduction_metrics(out, src)
    km, nm, _ = kept_weights(m, [i for i, q in enumerate(m.src) if q[2] > 0], out_notes, SETTINGS["M2"])
    r = {"n_in": len(m.src), "n_out": len(out_notes), "interventions": interventions,
         "kept_top": red["retention__top__kept"], "n_top": red["retention__top__n"],
         "kept_bass": red["retention__bass__kept"], "n_bass": red["retention__bass__n"],
         "kept_inner": red["retention__inner__kept"], "n_inner": red["retention__inner__n"],
         "m_kept_top": km["top"], "m_n_top": nm["top"], "harmony": harmony(out_notes, m.src)}
    if regime == "flute":
        ns = sorted((o, o + d) for _, o, d, _ in out_notes if d > 0)
        runs, start, prev, breaths = [], None, None, 0
        for a, b in ns:
            if prev is None or a - prev >= F(1, 2):
                if prev is not None:
                    breaths += 1
                    runs.append(float(prev - start))
                start = a
            prev = b if prev is None else max(prev, b)
        if prev is not None:
            runs.append(float(prev - start))
        r.update({"breaths": breaths, "dur_q": float(max(o + d for _, o, d, _ in m.src)),
                  "longest_run_q": max(runs, default=0.0)})
    return r


def _job(job):
    key, regime, mode = job
    import model.augment as A
    from arrangement.instruments import load_ensemble
    m = _W["val"][key]
    if mode == "topline":
        return regime, key, metrics(m, top_line(m), regime)
    ens = load_ensemble(ENS[regime])
    insts = [i.key for i in ens.instruments]
    if mode == "target":
        from model.targets_fk import build_flute, build_piano
        labs = (build_flute if regime == "flute" else build_piano)(m, Counter())
        inotes = [A.INote(o, d, x, part=p, octave=oc, real=re, src=sp) for (sp, o, d, x), (p, oc, re) in zip(m.src, labs)]
        inotes = [n for n in inotes]
        return regime, key, metrics(m, A.expand(inotes), regime)
    from model.decode import decode_movement
    inotes, com = decode_movement(_W["net"], "cpu", m.src, insts, ens, True, m.tpq, True)
    return regime, key, metrics(m, A.expand(inotes), regime, com.n_intervened)


def summarise(rows, regime):
    s = lambda f: sum(r[f] for r in rows)
    out = {"melody_exact": s("kept_top") / max(1, s("n_top")), "melody_M": s("m_kept_top") / max(1e-9, s("m_n_top")),
           "bass": s("kept_bass") / max(1, s("n_bass")), "inner": s("kept_inner") / max(1, s("n_inner")),
           "harmony": float(np.mean([r["harmony"] for r in rows])), "note_ratio": s("n_out") / s("n_in"),
           "interventions": s("interventions") / s("n_in")}
    if regime == "flute":
        out["breaths_per_32q"] = 32 * s("breaths") / s("dur_q")
        out["longest_run_q_median"] = float(np.median([r["longest_run_q"] for r in rows]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=[])
    ap.add_argument("--targets", action="store_true", help="also the F/K rule targets and the flute top line")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    from model.grpo import _val_keys
    keys = sorted(_val_keys())
    OUT.mkdir(parents=True, exist_ok=True)
    systems = [(r, "model") for r in a.runs] + ([("F/K target", "target"), ("top line", "topline")] if a.targets else [])
    res = {}
    for name, mode in systems:
        ck = str(ROOT / "model" / "results" / name / "checkpoint.pt") if mode == "model" else None
        regimes = ("flute",) if mode == "topline" else ("flute", "piano")
        with mp.get_context("fork").Pool(a.workers, initializer=_init, initargs=(ck,)) as pool:
            rows = pool.map(_job, [(k, r, mode) for r in regimes for k in keys], chunksize=1)
        res[name] = {r: summarise([x for rr, _, x in rows if rr == r], r) for r in regimes}
        print(name, json.dumps({r: {k: round(v, 3) for k, v in d.items()} for r, d in res[name].items()}), flush=True)
    tag = "_".join(n.replace("/", "_").replace(" ", "") for n, _ in systems)
    (OUT / f"dev_fk__{tag}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
