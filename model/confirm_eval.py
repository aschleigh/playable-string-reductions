"""R46 confirmatory evaluation (frozen in BLOCK4.md before the decodes). METRICS 1.5.0-draft, checker-v5.

    python -m model.confirm_eval

Systems (masked; plain records for the unmasked violation count): control-S2 (tested), arranger-v2b
(reference), control-S, all decoded melody-first by model/run_confirm.sh; plus checker-v5 Ou et al.
masked, continuity, naive from headroom/data/records. 145 evaluation movements (the 5 review movements
excluded). Paired 95% movement bootstrap (10,000, seed 0).

Criterion A = BLOCK4.md 2g (weighted fidelity A, unneeded DS per source note, interventions,
non-inferiority, detectors in the v2b-masked / continuity range under checker-v5).
Criterion B = per-part double stops at real-part levels, melody non-inferior, interventions down,
no rhythm rewriting (repeat share <= v2b, duration ratio delta CI lower > -0.05).
Writes model/results/confirm/{eval.json, CONFIRM.md}.
"""
from __future__ import annotations

import json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from arrangement.eval.harness import METRICS_VERSION, run as harness_run
from arrangement.eval.record import load, save

ROOT = Path(__file__).resolve().parents[1]
CF = ROOT / "model" / "results" / "confirm"
REC = ROOT / "headroom" / "data" / "records"
REVIEW_IDX = (22, 67, 39, 42, 148)
REAL_DS = {"trio": {"violin": 6.1, "viola": 5.1, "cello": 2.5}, "duo": {"violin": 6.1, "cello": 5.1}}
DETECTORS = {"note_ratio": ("texture", "note_ratio__total"), "doubling_rate": ("texture", "doubling_rate"),
             "polyphony_rate": ("texture", "polyphony_rate"), "rhythmic_independence": ("texture", "rhythmic_independence"),
             "duration_ratio": ("texture", "duration_ratio__total"), "harmony": ("fidelity", "harmony")}
TIERS = ("top", "inner", "bass")
WA = (1.0, 0.25, 0.8)          # setting A weights: top, inner, bass
N_BOOT = 10_000
MODELS = {"control-S2": "control-S2", "arranger-v2b": "arranger-v2b", "control-S": "control-S"}


def review_keys():
    return {json.loads((ROOT / "headroom" / "data" / "sources" / f"{i:03d}.json").read_text())["key"] for i in REVIEW_IDX}


def ds_counts(rec):
    """Per output part: (double-stop moments, non-grace notes)."""
    by = defaultdict(list)
    for p, o, d, x in rec.output.notes:
        if d > 0:
            by[p].append((o, o + d))
    out = {}
    for p in range(len(rec.output.parts)):
        ns = sorted(by.get(p, []))
        cnt, active, k = 0, [], 0
        for t in sorted({a for a, _ in ns}):
            while k < len(ns) and ns[k][0] <= t:
                active.append(ns[k]); k += 1
            active = [q for q in active if q[1] > t]
            cnt += len(active) >= 2
        out[p] = (cnt, len(ns))
    return out


def ratio_boot(num, den, idx):
    return num[idx].sum(1) / np.maximum(den[idx].sum(1), 1e-12)


def ci(x):
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


def main():
    rk = review_keys()
    res = {"metrics_version": METRICS_VERSION, "excluded_review_movements": sorted(rk)}
    md = [f"# Confirmatory test (R46): control-S2 vs arranger-v2b, checker-v5, METRICS {METRICS_VERSION}\n\n"
          "Melody-first decoding for all model systems; 145 evaluation movements (5 review movements excluded); "
          "paired 95% movement bootstrap.\n"]
    for regime in ("trio", "duo"):
        od = CF / "eval" / regime
        (od / "records").mkdir(parents=True, exist_ok=True)
        paths, recs, diags = [], {}, {}
        for name in MODELS:
            for sy, suf in (("arranger", ""), ("arranger_masked", "_masked")):
                src = CF / name / "records" / f"{sy}__{regime}.jsonl"
                dst = od / "records" / f"{name}{suf}__{regime}.jsonl"
                rs = load(src)
                for r in rs:
                    object.__setattr__(r, "system", name + suf)
                save(rs, dst)
                paths.append(dst)
                recs[name + suf] = {r.input_id: r for r in rs}
                diags[name + suf] = {d["input_id"]: d for d in json.loads((CF / name / "records" / f"{sy}__{regime}.diag.json").read_text())}
        for s in ("ou_band_masked", "continuity", "naive"):
            if (REC / f"{s}__{regime}.jsonl").exists():
                paths.append(REC / f"{s}__{regime}.jsonl")
                recs[s] = {r.input_id: r for r in load(REC / f"{s}__{regime}.jsonl")}
        harness_run([str(p) for p in paths], od / "harness", workers=24, soft=False)
        M = defaultdict(dict)
        for line in open(od / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            M[m["system"]][m["input_id"]] = m
        keys = sorted(set.intersection(*[set(v) for v in M.values()]) - rk)
        idx = np.random.default_rng(0).integers(0, len(keys), (N_BOOT, len(keys)))
        X, Y = M["control-S2_masked"], M["arranger-v2b_masked"]

        def red_sums(rows):
            kept = {t: np.array([rows[k]["reduction"][f"retention__{t}__kept"] for k in keys], float) for t in TIERS}
            n = {t: np.array([rows[k]["reduction"][f"retention__{t}__n"] for k in keys], float) for t in TIERS}
            return kept, n

        def fid(rows, f):
            vs = [rows[k]["fidelity"]["vs_source"] for k in keys]
            if f == "harmony":
                return np.array([v["harmony__sum"] for v in vs]), np.array([v["harmony__n_beats"] for v in vs], float)
            return np.array([v[f"{f}__sum"] for v in vs]), np.array([v[f"{f}__n_segments"] for v in vs], float)

        def paired(a_num, a_den, b_num, b_den):
            ba, bb = ratio_boot(a_num, a_den, idx), ratio_boot(b_num, b_den, idx)
            pa, pb = a_num.sum() / a_den.sum(), b_num.sum() / b_den.sum()
            return {"run": float(pa), "ref": float(pb), "delta": float(pa - pb), "ci95": ci(ba - bb)}
        D = {}
        kx, nx = red_sums(X); ky, ny = red_sums(Y)
        D["weighted_fidelity_A"] = paired(sum(w * kx[t] for w, t in zip(WA, TIERS)), sum(w * nx[t] for w, t in zip(WA, TIERS)),
                                          sum(w * ky[t] for w, t in zip(WA, TIERS)), sum(w * ny[t] for w, t in zip(WA, TIERS)))
        for t in TIERS:
            D[f"retention_{t}"] = paired(kx[t], nx[t], ky[t], ny[t])
        un = lambda R: np.array([R[k]["reduction"]["unneeded_double_stops"] for k in keys], float)
        ns = lambda R: np.array([R[k]["n_source_notes"] for k in keys], float)
        D["unneeded_ds_per_source_note"] = paired(un(X), ns(X), un(Y), ns(Y))
        for f in ("note_i_f1", "note_f1", "mel_top_f1", "harmony"):
            (sx, cx), (sy, cy) = fid(X, f), fid(Y, f)
            D[f] = paired(sx, cx, sy, cy)
        iv = lambda name: (np.array([diags[name][k]["masked_interventions"] for k in keys], float),
                           np.array([diags[name][k]["n_in"] for k in keys], float))
        (ix, nix), (iy, niy) = iv("control-S2_masked"), iv("arranger-v2b_masked")
        D["intervention_rate"] = paired(ix, nix, iy, niy)
        dr = lambda name: (np.array([diags[name][k]["n_drop"] for k in keys], float), np.array([diags[name][k]["n_in"] for k in keys], float))
        (dx, ndx), (dy, ndy) = dr("control-S2_masked"), dr("arranger-v2b_masked")
        D["drop_rate"] = paired(dx, ndx, dy, ndy)
        rep = lambda name: sum(diags[name][k]["realisation_counts"][1] + diags[name][k]["realisation_counts"][2] for k in keys) / \
            max(1, sum(sum(diags[name][k]["realisation_counts"]) for k in keys))
        durr = lambda R: np.array([np.nan if R[k]["texture"]["duration_ratio__total"] is None else R[k]["texture"]["duration_ratio__total"] for k in keys])
        dd = durr(X) - durr(Y)
        dur = {"run": float(np.nanmean(durr(X))), "ref": float(np.nanmean(durr(Y))), "delta": float(np.nanmean(dd)),
               "ci95": ci(np.array([np.nanmean(dd[i]) for i in idx]))}
        # per-part double stops (records)
        part_keys = list(REAL_DS[regime])
        ds = {}
        for sysname in ("control-S2_masked", "arranger-v2b_masked", "control-S_masked"):
            rows = [ds_counts(recs[sysname][k]) for k in keys]
            ds[sysname] = {}
            for p, inst in enumerate(part_keys):
                c = np.array([r[p][0] for r in rows], float); n = np.array([r[p][1] for r in rows], float)
                b = 100 * ratio_boot(c, n, idx)
                ds[sysname][inst] = {"per_100": float(100 * c.sum() / n.sum()), "ci95": ci(b)}
        # detectors (criterion A) in the range of v2b masked and continuity, widened to their bootstrap CIs
        det = {}
        C = M["continuity"]
        for name, (sec, f) in DETECTORS.items():
            val = lambda R, k: (R[k]["fidelity"]["vs_source"][f] if sec == "fidelity" else R[k][sec][f])
            lo, hi = np.inf, -np.inf
            for R in (Y, C):
                v = np.array([np.nan if val(R, k) is None else float(val(R, k)) for k in keys])
                b = np.array([np.nanmean(v[i]) for i in idx[:2000]])
                lo, hi = min(lo, np.percentile(b, 2.5)), max(hi, np.percentile(b, 97.5))
            v = float(np.nanmean([np.nan if val(X, k) is None else float(val(X, k)) for k in keys]))
            det[name] = {"value": v, "range": [float(lo), float(hi)], "inside": bool(lo <= v <= hi)}
        crit_a = {"1_weighted_fidelity_up": D["weighted_fidelity_A"]["ci95"][0] > 0,
                  "2_unneeded_ds_down": D["unneeded_ds_per_source_note"]["ci95"][1] < 0,
                  "3_interventions_down": D["intervention_rate"]["ci95"][1] < 0,
                  "4_noninferior": (D["retention_top"]["ci95"][0] > -0.01 and D["note_i_f1"]["ci95"][0] > -0.02
                                    and D["harmony"]["ci95"][0] > -0.02),
                  "5_detectors_inside": all(x["inside"] for x in det.values())}
        crit_b = {"1_double_stops_at_real_levels": all(ds["control-S2_masked"][i]["ci95"][1] <= REAL_DS[regime][i] for i in part_keys),
                  "2_melody_noninferior": D["retention_top"]["ci95"][0] > -0.01,
                  "3_interventions_down": D["intervention_rate"]["ci95"][1] < 0,
                  "4_no_rhythm_rewriting": rep("control-S2_masked") <= rep("arranger-v2b_masked") and dur["ci95"][0] > -0.05}
        hard = {s: float(np.mean([sum(v for k2, v in M[s][k]["playability"].items() if k2.endswith("__violations") and isinstance(v, (int, float)))
                                  for k in keys])) for s in ("control-S2_masked", "control-S2", "arranger-v2b", "arranger-v2b_masked")}
        res[regime] = {"n_movements": len(keys), "paired": D, "duration_ratio": dur,
                       "repeat_share": {s: rep(s) for s in ("control-S2_masked", "arranger-v2b_masked", "control-S_masked")},
                       "double_stops_per_part": ds, "real_part_rates": REAL_DS[regime], "detectors": det,
                       "criterion_A": crit_a, "criterion_A_holds": all(crit_a.values()),
                       "criterion_B": crit_b, "criterion_B_holds": all(crit_b.values()),
                       "mean_hard_violations_per_movement": hard}
        md.append(f"\n## {regime} ({len(keys)} movements): criterion B = {all(crit_b.values())}, criterion A = {all(crit_a.values())}\n\n")
        md.append("| Metric | arranger-v2b | control-S2 | Δ [95% CI] |\n|---|---|---|---|\n")
        for k, v in list(D.items()) + [("duration_ratio", dur)]:
            md.append(f"| {k} | {v['ref']:.3f} | {v['run']:.3f} | {v['delta']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] |\n")
        md.append("\n| Double stops per 100 notes | real parts | arranger-v2b | control-S | control-S2 [95% CI] |\n|---|---|---|---|---|\n")
        for i in part_keys:
            s2 = ds["control-S2_masked"][i]
            md.append(f"| {i} | {REAL_DS[regime][i]} | {ds['arranger-v2b_masked'][i]['per_100']:.1f} | {ds['control-S_masked'][i]['per_100']:.1f} | "
                      f"{s2['per_100']:.1f} [{s2['ci95'][0]:.1f}, {s2['ci95'][1]:.1f}] |\n")
        md.append(f"\nRepeat/tremolo share: v2b {rep('arranger-v2b_masked'):.3f}, S2 {rep('control-S2_masked'):.3f}. "
                  f"Hard violations per movement: S2 masked {hard['control-S2_masked']:.2f}, S2 unmasked {hard['control-S2']:.2f}, "
                  f"v2b unmasked {hard['arranger-v2b']:.2f}.\n")
        md.append("\n| Criterion B | Holds |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in crit_b.items()))
        md.append("\n| Criterion A (2g) | Holds |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in crit_a.items()))
        md.append("\n| Detector | S2 | range (v2b masked, continuity) | inside |\n|---|---|---|---|\n" +
                  "".join(f"| {k} | {v['value']:.3f} | [{v['range'][0]:.3f}, {v['range'][1]:.3f}] | {v['inside']} |\n" for k, v in det.items()))
    (CF / "eval.json").write_text(json.dumps(res, indent=1))
    (CF / "CONFIRM.md").write_text("".join(md))
    print("".join(md))


if __name__ == "__main__":
    main()
