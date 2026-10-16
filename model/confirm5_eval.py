"""BLOCK5.md Step 5: the Block 5 confirmatory evaluation (criterion C, frozen in BLOCK5.md, R51), checker-v5,
METRICS 1.5.0-draft, melody-first decoding, 145 evaluation movements (the 5 review movements excluded),
paired 95% movement bootstrap (10,000, seed 0). SECOND use of this evaluation set (R46 was the first).

    python -m model.confirm5_eval --tested <name> [--base control-S2b]

Records: model/results/confirm5/<name>/records/ (model/run_block5_c.sh); v2b's are R46's
(model/results/confirm/arranger-v2b/records, same checker, same decoder).
Criterion C, per regime:
  1. criterion B items 1-4 for the tested system against v2b masked;
  2. Δ mean idiomatic z (tested - base) CI lower bound > 0;
  3. Δ melody retention (count) vs base CI lower > -0.01, Δ harmony vs base CI lower > -0.02.
If the tested system is the base itself (no eligible RL setting), only criterion B is assessed.
Writes model/results/confirm5/{eval.json, CONFIRM5.md}.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

import model.idiom as I
from arrangement.eval.harness import METRICS_VERSION, run as harness_run
from arrangement.eval.record import load, save
from model.confirm_eval import N_BOOT, REAL_DS, TIERS, ci, ds_counts, ratio_boot, review_keys

ROOT = Path(__file__).resolve().parents[1]
C5 = ROOT / "model" / "results" / "confirm5"
C4 = ROOT / "model" / "results" / "confirm"


def rec_dir(name):
    return (C4 if name == "arranger-v2b" else C5) / name / "records"


def movement_z(net, calib, rec, regime, device):
    insts = [p.instrument for p in rec.output.parts]
    zs = []
    for p, inst in enumerate(insts):
        ns = [(o, d, x) for q, o, d, x in rec.output.notes if q == p and d > 0]
        z = I.part_z(net, calib, ns, inst, device, duo_cello=(regime == "duo" and inst == "cello"))
        if z == z:
            zs.append(z)
    return float(np.mean(zs)) if zs else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tested", required=True)
    ap.add_argument("--base", default="control-S2b")
    a = ap.parse_args()
    T, B, V = a.tested, a.base, "arranger-v2b"
    only_b = T == B
    names = [T, V] if only_b else [T, B, V]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net, calib = I.load(device)
    rk = review_keys()
    res = {"metrics_version": METRICS_VERSION, "tested": T, "base": B, "excluded_review_movements": sorted(rk),
           "caveat": "second confirmatory use of the 150-movement evaluation set (R46 first); weaker than a first look"}
    md = [f"# Block 5 confirmatory test: {T} (criterion C against {B}; criterion B against v2b)\n\n"
          f"checker-v5, METRICS {METRICS_VERSION}, melody-first decoding, 145 evaluation movements (5 review movements "
          "excluded), paired 95% movement bootstrap. **Caveat:** this is the evaluation set's second confirmatory use "
          "(R46 was the first, and its result was seen); it is weaker evidence than a first look.\n"]
    for regime in ("trio", "duo"):
        od = C5 / "eval" / regime
        (od / "records").mkdir(parents=True, exist_ok=True)
        paths, recs, diags = [], {}, {}
        for name in names:
            for sy, suf in (("arranger", ""), ("arranger_masked", "_masked")):
                rs = load(rec_dir(name) / f"{sy}__{regime}.jsonl")
                for r in rs:
                    object.__setattr__(r, "system", name + suf)
                dst = od / "records" / f"{name}{suf}__{regime}.jsonl"
                save(rs, dst)
                paths.append(dst)
                recs[name + suf] = {r.input_id: r for r in rs}
                diags[name + suf] = {d["input_id"]: d for d in json.loads((rec_dir(name) / f"{sy}__{regime}.diag.json").read_text())}
        harness_run([str(p) for p in paths], od / "harness", workers=16, soft=False)
        M = defaultdict(dict)
        for line in open(od / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            M[m["system"]][m["input_id"]] = m
        keys = sorted(set.intersection(*[set(v) for v in M.values()]) - rk)
        idx = np.random.default_rng(0).integers(0, len(keys), (N_BOOT, len(keys)))

        def red(rows, t):
            return (np.array([rows[k]["reduction"][f"retention__{t}__kept"] for k in keys], float),
                    np.array([rows[k]["reduction"][f"retention__{t}__n"] for k in keys], float))

        def harm(rows):
            vs = [rows[k]["fidelity"]["vs_source"] for k in keys]
            return np.array([v["harmony__sum"] for v in vs]), np.array([v["harmony__n_beats"] for v in vs], float)

        def paired(a_num, a_den, b_num, b_den):
            ba, bb = ratio_boot(a_num, a_den, idx), ratio_boot(b_num, b_den, idx)
            pa, pb = a_num.sum() / a_den.sum(), b_num.sum() / b_den.sum()
            return {"run": float(pa), "ref": float(pb), "delta": float(pa - pb), "ci95": ci(ba - bb)}

        def iv(name, f="masked_interventions"):
            return (np.array([diags[name][k][f] for k in keys], float), np.array([diags[name][k]["n_in"] for k in keys], float))

        def rep(name):
            return sum(diags[name][k]["realisation_counts"][1] + diags[name][k]["realisation_counts"][2] for k in keys) / \
                max(1, sum(sum(diags[name][k]["realisation_counts"]) for k in keys))

        def durr(R):
            return np.array([np.nan if R[k]["texture"]["duration_ratio__total"] is None else R[k]["texture"]["duration_ratio__total"] for k in keys])

        def compare(x, y):
            X, Y = M[x + "_masked"], M[y + "_masked"]
            D = {f"retention_{t}": paired(*red(X, t), *red(Y, t)) for t in TIERS}
            D["harmony"] = paired(*harm(X), *harm(Y))
            D["intervention_rate"] = paired(*iv(x + "_masked"), *iv(y + "_masked"))
            D["drop_rate"] = paired(*iv(x + "_masked", "n_drop"), *iv(y + "_masked", "n_drop"))
            dd = durr(X) - durr(Y)
            D["duration_ratio"] = {"run": float(np.nanmean(durr(X))), "ref": float(np.nanmean(durr(Y))), "delta": float(np.nanmean(dd)),
                                   "ci95": ci(np.array([np.nanmean(dd[i]) for i in idx]))}
            return D

        part_keys = list(REAL_DS[regime])
        ds = {}
        for name in names:
            rows = [ds_counts(recs[name + "_masked"][k]) for k in keys]
            ds[name] = {}
            for p, inst in enumerate(part_keys):
                c = np.array([r[p][0] for r in rows], float); n = np.array([r[p][1] for r in rows], float)
                ds[name][inst] = {"per_100": float(100 * c.sum() / n.sum()), "ci95": ci(100 * ratio_boot(c, n, idx))}
        DV = compare(T, V)
        crit_b = {"1_double_stops_at_real_levels": all(ds[T][i]["ci95"][1] <= REAL_DS[regime][i] for i in part_keys),
                  "2_melody_noninferior": DV["retention_top"]["ci95"][0] > -0.01,
                  "3_interventions_down": DV["intervention_rate"]["ci95"][1] < 0,
                  "4_no_rhythm_rewriting": rep(T + "_masked") <= rep(V + "_masked") and DV["duration_ratio"]["ci95"][0] > -0.05}
        Z = {name: np.array([movement_z(net, calib, recs[name + "_masked"][k], regime, device) for k in keys]) for name in names}
        out = {"n_movements": len(keys), "vs_v2b": DV, "double_stops_per_part": ds, "real_part_rates": REAL_DS[regime],
               "repeat_share": {n: rep(n + "_masked") for n in names}, "criterion_B": crit_b,
               "criterion_B_holds": all(crit_b.values()),
               "idiom_z": {n: float(np.nanmean(z)) for n, z in Z.items()}}
        if not only_b:
            DB = compare(T, B)
            dz = Z[T] - Z[B]
            DB["idiom_z"] = {"run": float(np.nanmean(Z[T])), "ref": float(np.nanmean(Z[B])), "delta": float(np.nanmean(dz)),
                             "ci95": ci(np.array([np.nanmean(dz[i]) for i in idx]))}
            crit_c = {"1_criterion_B": all(crit_b.values()), "2_more_idiomatic": DB["idiom_z"]["ci95"][0] > 0,
                      "3_noninferior_vs_base": DB["retention_top"]["ci95"][0] > -0.01 and DB["harmony"]["ci95"][0] > -0.02}
            out.update({"vs_base": DB, "criterion_C": crit_c, "criterion_C_holds": all(crit_c.values())})
        res[regime] = out
        head = f"criterion C = {out['criterion_C_holds']}, " if not only_b else ""
        md.append(f"\n## {regime} ({len(keys)} movements): {head}criterion B = {out['criterion_B_holds']}\n\n")
        for lab, D in (("vs arranger-v2b", DV),) + ((("vs " + B, out["vs_base"]),) if not only_b else ()):
            md.append(f"| {T} {lab} | reference | {T} | Δ [95% CI] |\n|---|---|---|---|\n")
            for k, v in D.items():
                md.append(f"| {k} | {v['ref']:.3f} | {v['run']:.3f} | {v['delta']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] |\n")
            md.append("\n")
        md.append("| Double stops per 100 notes | real parts | " + " | ".join(names) + " |\n|---|---|" + "---|" * len(names) + "\n")
        for i in part_keys:
            md.append(f"| {i} | {REAL_DS[regime][i]} | " + " | ".join(
                f"{ds[n][i]['per_100']:.1f} [{ds[n][i]['ci95'][0]:.1f}, {ds[n][i]['ci95'][1]:.1f}]" for n in names) + " |\n")
        md.append("\nMean idiomatic z: " + ", ".join(f"{n} {out['idiom_z'][n]:+.2f}" for n in names) + "\n")
        md.append("\n| Criterion B | Holds |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in crit_b.items()))
        if not only_b:
            md.append("\n| Criterion C | Holds |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in out["criterion_C"].items()))
    C5.mkdir(parents=True, exist_ok=True)
    (C5 / "eval.json").write_text(json.dumps(res, indent=1))
    (C5 / "CONFIRM5.md").write_text("".join(md))
    print("".join(md))


if __name__ == "__main__":
    main()
