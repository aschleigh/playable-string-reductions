"""Block 4 evaluation (BLOCK4.md 2b detector rule, 2g success criterion). METRICS 1.4.0-draft, checker-v4.

    python -m model.eval_rl ranges                      # fix the detector ranges (before any RL run)
    python -m model.eval_rl evaluate --run rl-C --setting C [--ref arranger-v2b]

`ranges`: per regime and detector, the range spanned by arranger-v2b masked and continuity, each widened
to its 95% movement-bootstrap CI. Written to model/results/rl/detector_ranges.json (and quoted in
BLOCK4.md); never recomputed after a run exists.

`evaluate`: the run's masked records (model/results/rl/<run>/records, from model.decode) and the
reference's, under the harness; paired movement bootstrap (10,000, seed 0) of
  1. weighted fidelity (the run's own setting)      success: CI lower > 0
  2. unneeded double stops per source note          success: CI upper < 0
  3. intervention rate                              success: CI upper < 0
  4. top-tier retention (CI lower > -0.01), Note_i F1 and harmony (CI lower > -0.02)
  5. every detector inside its fixed range
  6. reported: share of the ceiling gap closed, (run - ref) / (oracle_mask_model - ref)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from arrangement.eval.harness import run as harness_run
from arrangement.eval.record import load, save

ROOT = Path(__file__).resolve().parents[1]
M14 = ROOT / "model" / "results" / "metrics-1.4.0"
RL = ROOT / "model" / "results" / "rl"
REGIMES = ("trio", "duo")
DETECTORS = {   # name -> (section, field); movement means, as METRICS.md section 6
    "note_ratio": ("texture", "note_ratio__total"), "doubling_rate": ("texture", "doubling_rate"),
    "polyphony_rate": ("texture", "polyphony_rate"), "rhythmic_independence": ("texture", "rhythmic_independence"),
    "duration_ratio": ("texture", "duration_ratio__total"), "harmony": ("fidelity", "harmony"),
}
WEIGHTS = {"A": (1.0, 0.25, 0.8), "A2": (1.0, 0.25, 0.8), "A3": (1.0, 0.25, 0.8), "A3D9": (1.0, 0.25, 0.8), "B": (1.0, 0.7, 1.0), "C": (1.0, 1.0, 1.0)}   # top, inner, bass
TIERS = ("top", "inner", "bass")
N_BOOT = 10_000


def _rows(path, system):
    out = {}
    for line in open(path):
        m = json.loads(line)
        if m["system"] == system:
            out[m["input_id"]] = m
    return out


def _val(m, sec, f):
    v = m["fidelity"]["vs_source"].get(f) if sec == "fidelity" else m[sec].get(f)
    return np.nan if v is None else float(v)


def _boot_mean(x, idx):
    return np.nanmean(x[idx], 1)


def cmd_ranges(a):
    res = {}
    for regime in REGIMES:
        p = M14 / regime / "harness" / "metrics.jsonl"
        ref, cont = _rows(p, "arranger-v2b_masked"), _rows(p, "continuity")
        keys = sorted(set(ref) & set(cont))
        idx = np.random.default_rng(0).integers(0, len(keys), (N_BOOT, len(keys)))
        res[regime] = {}
        for name, (sec, f) in DETECTORS.items():
            lo, hi = np.inf, -np.inf
            for rows in (ref, cont):
                x = np.array([_val(rows[k], sec, f) for k in keys])
                b = _boot_mean(x, idx)
                lo, hi = min(lo, np.percentile(b, 2.5)), max(hi, np.percentile(b, 97.5))
            res[regime][name] = [float(lo), float(hi)]
    RL.mkdir(parents=True, exist_ok=True)
    (RL / a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def _ratio_boot(kept, n, idx):
    return kept[idx].sum(1) / np.maximum(n[idx].sum(1), 1)


def cmd_evaluate(a):
    ranges = json.loads((RL / a.ranges).read_text())
    rd = RL / a.run
    out = {"run": a.run, "ref": a.ref, "setting": a.setting}
    for regime in REGIMES:
        rec = rd / "records" / f"arranger_masked__{regime}.jsonl"
        if not rec.exists():
            continue
        od = rd / "eval" / regime
        mine = od / f"{a.run}_masked__{regime}.jsonl"
        if not mine.exists():
            recs = load(rec)
            for r in recs:
                object.__setattr__(r, "system", f"{a.run}_masked")
            od.mkdir(parents=True, exist_ok=True)
            save(recs, mine)
        ref_rec = M14 / regime / "records" / f"{a.ref}_masked__{regime}.jsonl"
        orc = ROOT / "model" / "results" / "diagnostics" / "records" / f"oracle_mask_model__{regime}.jsonl"
        harness_run([str(mine), str(ref_rec), str(orc)], od / "harness", workers=a.workers, soft=False)
        P = od / "harness" / "metrics.jsonl"
        X, Y, O = _rows(P, f"{a.run}_masked"), _rows(P, f"{a.ref}_masked"), _rows(P, "oracle_mask_model")
        keys = sorted(set(X) & set(Y) & set(O))
        idx = np.random.default_rng(0).integers(0, len(keys), (N_BOOT, len(keys)))
        w = WEIGHTS[a.setting]

        def red(rows):
            kept = {t: np.array([rows[k]["reduction"][f"retention__{t}__kept"] for k in keys], float) for t in TIERS}
            n = {t: np.array([rows[k]["reduction"][f"retention__{t}__n"] for k in keys], float) for t in TIERS}
            wk = sum(wi * kept[t] for wi, t in zip(w, TIERS)); wn = sum(wi * n[t] for wi, t in zip(w, TIERS))
            un = np.array([rows[k]["reduction"]["unneeded_double_stops"] for k in keys], float)
            ns = np.array([rows[k]["n_source_notes"] for k in keys], float)
            return kept, n, wk, wn, un, ns

        def fid(rows, f):
            s = np.array([rows[k]["fidelity"]["vs_source"][f"{f}__sum"] if f != "harmony" else rows[k]["fidelity"]["vs_source"]["harmony__sum"] for k in keys])
            c = np.array([rows[k]["fidelity"]["vs_source"][f"{f}__n_segments"] if f != "harmony" else rows[k]["fidelity"]["vs_source"]["harmony__n_beats"] for k in keys])
            return s, c
        kx, nx, wkx, wnx, unx, nsx = red(X)
        ky, ny, wky, wny, uny, nsy = red(Y)
        ko, no, wko, wno, _, _ = red(O)
        D = {}

        def paired(name, bx, by, px, py):
            d = bx - by
            D[name] = {"run": float(px), "ref": float(py), "delta": float(px - py),
                       "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}
        paired("weighted_fidelity", _ratio_boot(wkx, wnx, idx), _ratio_boot(wky, wny, idx), wkx.sum() / wnx.sum(), wky.sum() / wny.sum())
        paired("unneeded_ds_per_source_note", _ratio_boot(unx, nsx, idx), _ratio_boot(uny, nsy, idx), unx.sum() / nsx.sum(), uny.sum() / nsy.sum())
        for t in TIERS:
            paired(f"retention_{t}", _ratio_boot(kx[t], nx[t], idx), _ratio_boot(ky[t], ny[t], idx), kx[t].sum() / nx[t].sum(), ky[t].sum() / ny[t].sum())
        for f in ("note_i_f1", "note_f1", "mel_top_f1", "harmony"):
            (sx, cx), (sy, cy) = fid(X, f), fid(Y, f)
            paired(f, _ratio_boot(sx, cx, idx), _ratio_boot(sy, cy, idx), sx.sum() / cx.sum(), sy.sum() / cy.sum())
        # intervention rate, from the decode diagnostics
        dx = {d["input_id"]: d for d in json.loads((rd / "records" / f"arranger_masked__{regime}.diag.json").read_text())}
        dy = {d["input_id"]: d for d in json.loads((ROOT / "model" / "results" / a.ref / "records" / f"arranger_masked__{regime}.diag.json").read_text())}
        ix = np.array([dx[k]["masked_interventions"] for k in keys], float); nix = np.array([dx[k]["n_in"] for k in keys], float)
        iy = np.array([dy[k]["masked_interventions"] for k in keys], float); niy = np.array([dy[k]["n_in"] for k in keys], float)
        paired("intervention_rate", _ratio_boot(ix, nix, idx), _ratio_boot(iy, niy, idx), ix.sum() / nix.sum(), iy.sum() / niy.sum())
        det = {}
        for name, (sec, f) in DETECTORS.items():
            v = float(np.nanmean([_val(X[k], sec, f) for k in keys]))
            lo, hi = ranges[regime][name]
            det[name] = {"value": v, "range": [lo, hi], "inside": lo <= v <= hi}
        crit = {
            "1_weighted_fidelity_up": D["weighted_fidelity"]["ci95"][0] > 0,
            "2_unneeded_ds_down": D["unneeded_ds_per_source_note"]["ci95"][1] < 0,
            "3_interventions_down": D["intervention_rate"]["ci95"][1] < 0,
            "4_noninferior": (D["retention_top"]["ci95"][0] > -0.01 and D["note_i_f1"]["ci95"][0] > -0.02
                              and D["harmony"]["ci95"][0] > -0.02),
            "5_detectors_inside": all(x["inside"] for x in det.values()),
        }
        gap = {}
        for name, (o_num, o_den) in {"weighted_fidelity": (wko.sum(), wno.sum()),
                                     **{f"retention_{t}": (ko[t].sum(), no[t].sum()) for t in TIERS}}.items():
            oc = o_num / o_den
            gap[name] = (D[name]["run"] - D[name]["ref"]) / (oc - D[name]["ref"]) if oc != D[name]["ref"] else None
        out[regime] = {"n_movements": len(keys), "paired": D, "detectors": det, "criteria": crit,
                       "success": all(crit.values()), "ceiling_gap_closed": gap}
    (rd / f"eval{a.suffix}.json").write_text(json.dumps(out, indent=1))
    md = [f"# {a.run} (setting {a.setting}) vs {a.ref}, masked, METRICS 1.4.0-draft\n"]
    for regime in REGIMES:
        if regime not in out:
            continue
        R = out[regime]
        md.append(f"\n## {regime} ({R['n_movements']} movements): success = {R['success']}\n\n| Metric | {a.ref} | {a.run} | Δ [95% CI] |\n|---|---|---|---|\n")
        for k, v in R["paired"].items():
            md.append(f"| {k} | {v['ref']:.4f} | {v['run']:.4f} | {v['delta']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}] |\n")
        md.append("\n| Criterion | Holds |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in R["criteria"].items()))
        md.append("\n| Detector | Value | Fixed range | Inside |\n|---|---|---|---|\n" + "".join(
            f"| {k} | {v['value']:.3f} | [{v['range'][0]:.3f}, {v['range'][1]:.3f}] | {v['inside']} |\n" for k, v in R["detectors"].items()))
        md.append("\nCeiling gap closed: " + ", ".join(f"{k} {'—' if v is None else f'{v:+.2f}'}" for k, v in R["ceiling_gap_closed"].items()) + "\n")
    (rd / f"eval{a.suffix}.md").write_text("".join(md))
    print("".join(md))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rg = sub.add_parser("ranges")
    rg.add_argument("--out", default="detector_ranges.json")
    e = sub.add_parser("evaluate")
    e.add_argument("--run", required=True)
    e.add_argument("--setting", required=True, choices=list(WEIGHTS))
    e.add_argument("--ref", default="arranger-v2b")
    e.add_argument("--workers", type=int, default=24)
    e.add_argument("--suffix", default="", help="output name suffix (e.g. control S under several settings)")
    e.add_argument("--ranges", default="detector_ranges.json", help="detector ranges file in model/results/rl")
    a = ap.parse_args(argv)
    cmd_ranges(a) if a.cmd == "ranges" else cmd_evaluate(a)


if __name__ == "__main__":
    main()
