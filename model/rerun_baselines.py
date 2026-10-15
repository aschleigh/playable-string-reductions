"""METRICS 1.4.0-draft baseline re-run (BLOCK4.md 2f, Step 4). Every existing record, every regime.

    python -m model.rerun_baselines [--regimes trio duo ...] [--workers 24]

Systems per regime (whatever exists):
  headroom/data/records/<sys>__<regime>.jsonl   Ou et al. (current = checker-v4 masked), repair, continuity,
                                                naive, control, AMT (secondary), floor (quartet human score)
  model/results/diagnostics/records/            the four oracles (BLOCK4.md 1a)
  model/results/<run>/records/                  arranger-v1, arranger-v2, arranger-v2b (plain, masked),
                                                renamed "<run>" / "<run>_masked" so runs do not collide
Writes model/results/metrics-1.4.0/<regime>/{harness/, summary.json, table.md}.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from arrangement.eval.harness import METRICS_VERSION, run
from arrangement.eval.record import load, save
from model.evaluate import summarise

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "headroom" / "data" / "records"
DIAG = ROOT / "model" / "results" / "diagnostics" / "records"
OUT = ROOT / "model" / "results" / "metrics-1.4.0"
HEADROOM_SYS = ["ou_band", "ou_band_masked", "ou_band_repair", "ou_piano", "ou_piano_masked", "ou_piano_repair",
                "continuity", "naive", "control", "floor", "amt"]
ORACLES = ["oracle", "oracle_mask_drop", "oracle_mask_repair", "oracle_mask_model"]
RUNS = ["arranger-v1", "arranger-v2", "arranger-v2b"]
TIERS = ("top", "inner", "bass")


def model_paths(regime, od):
    paths, inter = [], {}
    for run_name in RUNS:
        for sy, suffix in (("arranger", ""), ("arranger_masked", "_masked")):
            p = ROOT / "model" / "results" / run_name / "records" / f"{sy}__{regime}.jsonl"
            if not p.exists():
                continue
            name = run_name + suffix
            dst = od / "records" / f"{name}__{regime}.jsonl"
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                recs = load(p)
                for r in recs:
                    object.__setattr__(r, "system", name)
                save(recs, dst)
            paths.append(dst)
            dg = p.parent / f"{sy}__{regime}.diag.json"
            if suffix and dg.exists():
                d = json.loads(dg.read_text())
                if "masked_interventions" in d[0]:
                    inter[name] = sum(x["masked_interventions"] for x in d) / sum(x["n_in"] for x in d)
    if "arranger-v1_masked" in [p.stem.split("__")[0] for p in paths]:   # v1 diag predates the counter (BLOCK4.md 1c)
        inter.setdefault("arranger-v1_masked", {"trio": 0.1185, "duo": 0.2216}.get(regime))
    return paths, inter


def pooled_reduction(rows):
    red = [r["reduction"] for r in rows]
    out = {}
    for t in TIERS:
        k, n = sum(x[f"retention__{t}__kept"] for x in red), sum(x[f"retention__{t}__n"] for x in red)
        out[f"retention__{t}"] = k / n if n else None
    W = {"A": (1.0, 0.25, 0.8), "B": (1.0, 0.7, 1.0), "C": (1.0, 1.0, 1.0)}
    for s, w in W.items():
        num = sum(wi * sum(x[f"retention__{t}__kept"] for x in red) for wi, t in zip(w, TIERS))
        den = sum(wi * sum(x[f"retention__{t}__n"] for x in red) for wi, t in zip(w, TIERS))
        out[f"weighted_fidelity__{s}"] = num / den if den else None
    un = sum(x["unneeded_double_stops"] for x in red)
    n_out = sum(r["n_output_notes"] for r in rows)
    n_src = sum(r["n_source_notes"] for r in rows)
    out["unneeded_double_stops__per_100"] = 100 * un / n_out if n_out else None
    out["unneeded_double_stops__per_100_source"] = 100 * un / n_src if n_src else None
    out["double_stop_events__per_100"] = 100 * sum(x["double_stop_events"] for x in red) / n_out if n_out else None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", nargs="+", default=["trio", "duo", "quartet", "solo_violin", "solo_flute", "piano"])
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args(argv)
    for regime in a.regimes:
        od = OUT / regime
        paths = [REC / f"{s}__{regime}.jsonl" for s in HEADROOM_SYS if (REC / f"{s}__{regime}.jsonl").exists()]
        paths += [DIAG / f"{s}__{regime}.jsonl" for s in ORACLES if (DIAG / f"{s}__{regime}.jsonl").exists()]
        mp, inter = model_paths(regime, od)
        paths += mp
        run([str(p) for p in paths], od / "harness", workers=a.workers, soft=False)
        metrics: dict[str, list] = {}
        for line in open(od / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            metrics.setdefault(m["system"], []).append(m)
        amt = metrics.pop("amt", None)
        keys = sorted(set.intersection(*[{r["input_id"] for r in rs} for rs in metrics.values()]))
        idx = np.random.default_rng(0).integers(0, len(keys), (10_000, len(keys)))
        S = summarise(metrics, keys, idx)
        for sy, rs in metrics.items():
            S[sy]["reduction"] = pooled_reduction([r for r in rs if r["input_id"] in set(keys)])
            S[sy]["intervention_rate"] = inter.get(sy)
        if amt:
            ak = sorted({r["input_id"] for r in amt})
            aidx = np.random.default_rng(0).integers(0, len(ak), (10_000, len(ak)))
            S["amt (secondary, 32 bars)"] = summarise({"amt": amt}, ak, aidx)["amt"]
            S["amt (secondary, 32 bars)"]["reduction"] = pooled_reduction(amt)
        (od / "summary.json").write_text(json.dumps({"metrics_version": METRICS_VERSION, "regime": regime,
                                                     "n_movements": len(keys), "systems": S}, indent=1))
        md = [f"## {regime} ({len(keys)} movements, METRICS {METRICS_VERSION}, checker-v4)\n\n",
              "| System | D (check) | Note_i F1 | Note F1 | Mel F1 | Harmony | Retention top / inner / bass | "
              "WF A / B | Unneeded double stops /100 | Interventions | Note ratio |\n|" + "---|" * 11 + "\n"]
        for sy, r in S.items():
            f, x, t = r["fidelity"], r["reduction"], r["texture"]
            ret = " / ".join("—" if x[f"retention__{k}"] is None else f"{x[f'retention__{k}']:.3f}" for k in TIERS)
            iv = "" if r.get("intervention_rate") is None else f"{r['intervention_rate']:.3f}"
            md.append(f"| {sy} | {r['D']:.2f} ({r['D_check']}) | {f['note_i_f1']:.3f} | {f['note_f1']:.3f} | "
                      f"{f['mel_f1']:.3f} | {f['harmony']:.3f} | {ret} | {x['weighted_fidelity__A']:.3f} / "
                      f"{x['weighted_fidelity__B']:.3f} | {x['unneeded_double_stops__per_100']:.1f} | {iv} | "
                      f"{t['note_ratio__total']:.3f} |\n")
        (od / "table.md").write_text("".join(md))
        print("".join(md), flush=True)


if __name__ == "__main__":
    main()
