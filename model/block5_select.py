"""BLOCK5.md selection rules, on the dev split only (61 movements, masked, melody-first).

    python -m model.block5_select base                         Step 1c: control-S2b vs control-S2
    python -m model.block5_select rl --base rl/control-S2b --runs rl/rl-B5-MI05 rl/rl-B5-MI10    Step 4 rule

Inputs: model/results/idiom/dev_outputs/<run>.pkl (model/dev_outputs.py) and
model/results/rl/dev_decode_compare_<tag>.json (model/dev_decode_compare.py, the "v3 melody-first" rows).
Writes model/results/idiom/select_<mode>.json.
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch

import model.idiom as I
from model.idiom_gate import SLOTS

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "model" / "results" / "idiom" / "dev_outputs"
RLD = ROOT / "model" / "results" / "rl"
DS_MAX = {"trio": {"violin": 6.1, "viola": 5.1, "cello": 2.5}, "duo": {"violin": 6.1, "cello": 5.1}}   # criterion B item 1


def ds_moments(ns):
    ns = sorted((F(o), F(d)) for o, d, _ in ns if F(d) > 0)
    cnt, act, k = 0, [], 0
    for t in sorted({o for o, _ in ns}):
        while k < len(ns) and ns[k][0] <= t:
            act.append(ns[k]); k += 1
        act = [q for q in act if q[0] + q[1] > t]
        cnt += len(act) >= 2
    return cnt


def harmony(out_notes, src_notes):
    from model.grpo import chroma_per_beat
    end = max(F(o) + F(d) for _, o, d, _ in src_notes)
    Cs = chroma_per_beat(tuple(src_notes), F(0), end)
    Co = chroma_per_beat(tuple(out_notes), F(0), end)
    nb, na = np.linalg.norm(Cs, axis=1), np.linalg.norm(Co, axis=1)
    sel = nb > 0
    return float(np.where(na[sel] > 0, (Co[sel] * Cs[sel]).sum(1) / np.maximum(na[sel] * nb[sel], 1e-300), 0).mean())


def dev_stats(run, net, calib, device, src):
    S = pickle.load(open(DEV / f"{run.replace('/', '_')}.pkl", "rb"))
    out = {}
    for regime in ("trio", "duo"):
        insts = next(iter(S[regime].values()))["insts"]
        ds = defaultdict(lambda: [0, 0])
        z = defaultdict(list)
        H = []
        for key, d in S[regime].items():
            for p, inst in enumerate(insts):
                ns = [(o, du, x) for q, o, du, x in d["notes"] if q == p]
                ds[inst][0] += ds_moments(ns); ds[inst][1] += len(ns)
                z[inst].append(I.part_z(net, calib, ns, inst, device, duo_cello=(regime == "duo" and inst == "cello")))
            H.append(harmony(d["notes"], src[key]))
        out[regime] = {"ds_per_100": {i: 100 * a / max(1, b) for i, (a, b) in ds.items()},
                       "z": {i: float(np.nanmean(v)) for i, v in z.items()},
                       "z_mean": float(np.nanmean([np.nanmean(v) for v in z.values()])),
                       "harmony": float(np.mean(H))}
    return out


def compare_rows(tag, run):
    c = json.loads((RLD / f"dev_decode_compare_{tag}.json").read_text())
    return c[f"{run} | v3 melody-first"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["base", "rl"])
    ap.add_argument("--base", default="rl/control-S2b")
    ap.add_argument("--runs", nargs="*", default=[])
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net, calib = I.load(device)
    src = {}
    for line in open(ROOT / "model" / "data" / "val.jsonl"):
        d = json.loads(line)
        src[d["key"]] = [(int(p), F(o), F(du), int(x)) for p, o, du, x in d["notes"]]
    res = {}
    if a.mode == "base":
        s2, s2b = dev_stats("rl/control-S2", net, calib, device, src), dev_stats("rl/control-S2b", net, calib, device, src)
        c2, c2b = compare_rows("S2", "rl/control-S2"), compare_rows("S2b", "rl/control-S2b")
        mel = {r: (c2b[f"val_{r}/top_retention_M"], c2[f"val_{r}/top_retention_M"]) for r in ("trio", "duo")}
        viola_falls = s2b["trio"]["ds_per_100"]["viola"] < s2["trio"]["ds_per_100"]["viola"]
        mel_ok = all(b >= o - 0.005 for b, o in mel.values())
        res = {"control-S2": s2, "control-S2b": s2b, "melody_duration": mel, "viola_falls": viola_falls,
               "melody_ok": mel_ok, "replace": bool(viola_falls and mel_ok),
               "compare": {"control-S2": c2, "control-S2b": c2b}}
        print(json.dumps({k: v for k, v in res.items() if k != "compare"}, indent=1))
    else:
        v2 = json.loads((RLD / "dev_decode_compare_v2b.json").read_text())["arranger-v2b | v3 melody-first"]
        tagb = "S2b" if a.base.endswith("S2b") else "S2"
        cb = compare_rows(tagb, a.base)
        base = dev_stats(a.base, net, calib, device, src)
        res["base"] = {"run": a.base, **base}
        elig = {}
        for run in a.runs:
            st = dev_stats(run, net, calib, device, src)
            c = compare_rows(run.split("/")[-1], run)
            checks = {}
            for r in ("trio", "duo"):
                checks[r] = {
                    "melody": c[f"val_{r}/top_retention_M"] >= cb[f"val_{r}/top_retention_M"] - 0.005,
                    "interventions": c[f"val_{r}/intervention_rate"] <= cb[f"val_{r}/intervention_rate"] + 0.005,
                    "double_stops": all(st[r]["ds_per_100"][i] <= DS_MAX[r][i] for i in DS_MAX[r]),
                    "repeat_share": c[f"val_{r}/repeat_op_share"] <= v2[f"val_{r}/repeat_op_share"] + 1e-9,
                    "mean_dur_ratio": c[f"val_{r}/mean_dur_ratio"] >= cb[f"val_{r}/mean_dur_ratio"] - 0.05,
                }
            ok = all(all(v.values()) for v in checks.values())
            zm = float(np.mean([st[r]["z_mean"] for r in ("trio", "duo")]))
            hm = float(np.mean([st[r]["harmony"] for r in ("trio", "duo")]))
            res[run] = {**st, "checks": checks, "eligible": ok, "z_mean": zm, "harmony_mean": hm, "compare": c}
            if ok:
                elig[run] = (zm, hm)
        if not elig:
            res["selected"] = None
        else:
            best = max(elig, key=lambda r: elig[r][0])
            ties = [r for r in elig if elig[best][0] - elig[r][0] < 0.1]
            res["selected"] = max(ties, key=lambda r: elig[r][1])
        print(json.dumps({k: (v if k in ("selected",) else {kk: vv for kk, vv in v.items() if kk != "compare"})
                          for k, v in res.items() if isinstance(v, dict) or k == "selected"}, indent=1, default=str))
    (ROOT / "model" / "results" / "idiom" / f"select_{a.mode}.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
