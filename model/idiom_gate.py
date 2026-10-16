"""BLOCK5.md Step 3: the validation gate for the idiomatic part model P, on the dev split only.

    python -m model.idiom_gate --base rl/control-S2b      -> model/results/idiom/gate.json, gate.md

Per output slot (trio violin / viola / cello, duo violin / cello), the part z under P for: real dev parts,
control-S2(b), v2b and the hacked outputs. Pass rule (fixed in BLOCK5.md before P was trained, R51):
  - AUC(real > base) >= 0.70 and AUC(base > v2b) >= 0.70 in every slot;
  - AUC(v2b > hack) >= 0.90 for every hack, in every slot.
Hacks: rl-AZ2 (a real repeat-op reward hack, decoded), and four built from v2b's outputs:
  restrike16 (every note re-struck as 16ths), up2oct (every part two octaves up), shuffle (each note to a
  random part), dyads (every note doubled a major third below, sounding together).
"""
from __future__ import annotations

import argparse
import json
import pickle
import random
import zlib
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch

import model.idiom as I

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "model" / "results" / "idiom" / "dev_outputs"
SLOTS = [("trio", 0, "violin"), ("trio", 1, "viola"), ("trio", 2, "cello"), ("duo", 0, "violin"), ("duo", 1, "cello")]


def hacks(notes, nparts, seed):
    rng = random.Random(seed)
    out = {"restrike16": [], "up2oct": [], "shuffle": [], "dyads": []}
    q = F(1, 4)
    for p, o, d, x in notes:
        k = max(1, int(F(d) / q))
        out["restrike16"] += [(p, F(o) + j * q, q if j < k - 1 else F(d) - (k - 1) * q, x) for j in range(k)]
        out["up2oct"].append((p, o, d, x + 24))
        out["shuffle"].append((rng.randrange(nparts), o, d, x))
        out["dyads"] += [(p, o, d, x), (p, o, d, x - 4)]
    return out


def slot_z(net, calib, notes, part, regime, inst, device):
    ns = [(o, d, x) for p, o, d, x in notes if p == part]
    return I.part_z(net, calib, ns, inst, device, duo_cello=(regime == "duo" and inst == "cello"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="rl/control-S2b")
    ap.add_argument("--others", nargs="*", default=["rl/control-S2"])
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net, calib = I.load(device)
    systems = {r: pickle.load(open(DEV / f"{r.replace('/', '_')}.pkl", "rb"))
               for r in ["arranger-v2b", a.base, "rl/rl-AZ2", *a.others]}
    real = defaultdict(lambda: defaultdict(list))         # key -> source part -> notes
    for line in open(ROOT / "model" / "data" / "val.jsonl"):
        d = json.loads(line)
        for p, o, du, x in d["notes"]:
            real[d["key"]][int(p)].append((F(o), F(du), int(x)))
    Z = defaultdict(lambda: defaultdict(list))            # slot -> group -> [z]
    keys = sorted(systems["arranger-v2b"]["trio"])
    for regime, part, inst in SLOTS:
        sl = f"{regime}/{inst}"
        for key in keys:
            srcp = {"violin": (0, 1), "viola": (2,), "cello": (3,) if regime == "trio" else (3, 2)}[inst]
            for sp in srcp:
                as_inst = I.SRC_INST[sp]
                Z[sl]["real"].append(I.part_z(net, calib, real[key][sp], as_inst, device,
                                              duo_cello=(regime == "duo" and inst == "cello")))
            for run, S in systems.items():
                Z[sl][run].append(slot_z(net, calib, S[regime][key]["notes"], part, regime, inst, device))
            v = systems["arranger-v2b"][regime][key]
            for h, ns in hacks(v["notes"], len(v["insts"]), zlib.crc32(key.encode()) % 1000).items():
                Z[sl][f"hack:{h}"].append(slot_z(net, calib, ns, part, regime, inst, device))
        print(sl, {g: round(float(np.nanmean(z)), 2) for g, z in Z[sl].items()}, flush=True)
    res, ok = {}, True
    for sl, G in Z.items():
        r = {"mean_z": {g: float(np.nanmean(z)) for g, z in G.items()},
             "auc_real_gt_base": I.auc(G["real"], G[a.base]),
             "auc_base_gt_v2b": I.auc(G[a.base], G["arranger-v2b"]),
             **{f"auc_v2b_gt_{h}": I.auc(G["arranger-v2b"], G[h]) for h in G if h.startswith("hack:") or h == "rl/rl-AZ2"}}
        for o in a.others:
            r[f"auc_{o}_gt_v2b"] = I.auc(G[o], G["arranger-v2b"])
        r["pass"] = (r["auc_real_gt_base"] >= 0.70 and r["auc_base_gt_v2b"] >= 0.70
                     and all(v >= 0.90 for k, v in r.items() if k.startswith("auc_v2b_gt_")))
        ok &= r["pass"]
        res[sl] = r
    res["PASS"] = ok
    out = ROOT / "model" / "results" / "idiom"
    (out / "gate.json").write_text(json.dumps(res, indent=1))
    groups = list(next(iter(Z.values())).keys())
    md = ["| slot | " + " | ".join(groups) + " | real>base | base>v2b | min v2b>hack | pass |", "|" + "---|" * (len(groups) + 5)]
    for sl, r in res.items():
        if sl == "PASS":
            continue
        mh = min(v for k, v in r.items() if k.startswith("auc_v2b_gt_"))
        md.append(f"| {sl} | " + " | ".join(f"{r['mean_z'][g]:.2f}" for g in groups)
                  + f" | {r['auc_real_gt_base']:.2f} | {r['auc_base_gt_v2b']:.2f} | {mh:.2f} | {'yes' if r['pass'] else 'NO'} |")
    md.append(f"\n**Gate: {'PASS' if ok else 'FAIL'}** (base {a.base}).")
    (out / "gate.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
