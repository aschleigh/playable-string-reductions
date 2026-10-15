"""Step 5 evaluation: the trained arranger (with and without masking) against every reference
system, all under the frozen harness (METRICS.md, current version) and checker.

    python -m model.evaluate --run arranger-v1 --regimes trio duo [--workers N]

Systems per regime (whatever records exist):
  arranger, arranger_masked                 model/results/<run>/records/
  ou_band, ou_band_masked, ou_band_repair    headroom/data/records/  (masked = current checker's run)
  continuity, naive, amt (trio, secondary)   headroom/data/records/

Per system, pooled over the movements every compared system covers (AMT separately; it covers
32 bars): D = worst single check per 100 notes with a 95% movement bootstrap CI, every check's
rate, fidelity vs source (Note_i F1, Note F1, Mel F1, harmony), texture detectors (polyphony
rate, rhythmic independence, doubling rate, note ratio; mean over movements, source value
alongside). Paired deltas (system - reference) with 95% bootstrap CIs for the model rows
against continuity, masked Ou and Ou + repair.

Success criterion (brief, Step 5): match continuity on playability while beating it on fidelity
and texture. Every number is reported; nothing is combined into one score.
Writes model/results/<run>/eval/<regime>/{harness/, eval.json, table.md}.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from arrangement.checker import CHECKS
from arrangement.eval.harness import METRICS_VERSION, run
from decoding.gate import FID, _stats

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "headroom" / "data" / "records"
N_BOOT, SEED = 10_000, 0
TEX = ["polyphony_rate", "rhythmic_independence", "doubling_rate", "note_ratio__total"]
REFS = ["continuity", "ou_band_masked", "ou_band_repair"]


def _tex(rows, k):
    v = np.array([np.nan if r["texture"].get(k) is None else float(r["texture"][k]) for r in rows])
    s = np.array([np.nan if r["texture"].get(f"{k}__source") is None else float(r["texture"][f"{k}__source"])
                  for r in rows]) if k != "note_ratio__total" else np.ones(len(rows))
    return v, s


def summarise(metrics: dict[str, list[dict]], keys: list[str], idx) -> dict:
    out = {}
    for sy, rs in metrics.items():
        rows = sorted([r for r in rs if r["input_id"] in set(keys)], key=lambda r: r["input_id"])
        s = _stats(rows)
        rates = 100 * s["viol"].sum(0) / s["notes"].sum()
        bv = 100 * s["viol"][idx].sum(1) / s["notes"][idx].sum(1)[:, None]
        D = bv.max(1)
        row = {"n_movements": len(rows), "n_notes": int(s["notes"].sum()), "D": float(rates.max()),
               "D_check": CHECKS[int(rates.argmax())],
               "D_ci95": [float(np.percentile(D, 2.5)), float(np.percentile(D, 97.5))],
               "per_100": dict(zip(CHECKS, map(float, rates))),
               "fidelity": {k: float(sm.sum() / c.sum()) for k, (sm, c) in s["fid"].items()},
               "texture": {}}
        for k in TEX:
            v, src = _tex(rows, k)
            row["texture"][k] = float(np.nanmean(v))
            row["texture"][f"{k}__source"] = float(np.nanmean(src))
        out[sy] = row
    return out


def deltas(metrics, keys, idx, a: str, b: str) -> dict:
    ra = sorted([r for r in metrics[a] if r["input_id"] in set(keys)], key=lambda r: r["input_id"])
    rb = sorted([r for r in metrics[b] if r["input_id"] in set(keys)], key=lambda r: r["input_id"])
    sa, sb = _stats(ra), _stats(rb)
    out = {}
    for k in FID:
        (xa, ca), (xb, cb) = sa["fid"][k], sb["fid"][k]
        point = xa.sum() / ca.sum() - xb.sum() / cb.sum()
        boot = xa[idx].sum(1) / ca[idx].sum(1) - xb[idx].sum(1) / cb[idx].sum(1)
        out[k] = {"delta": float(point), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
    for k in TEX:
        va, _ = _tex(ra, k)
        vb, _ = _tex(rb, k)
        d = va - vb
        ok = ~np.isnan(d)
        boot = np.array([np.nanmean(d[i]) for i in idx[:2000]])
        out[k] = {"delta": float(np.nanmean(d[ok])), "ci95": [float(np.nanpercentile(boot, 2.5)),
                                                             float(np.nanpercentile(boot, 97.5))]}
    for name, s in (("D_a", sa), ("D_b", sb)):
        pass
    va = 100 * sa["viol"][idx].sum(1) / sa["notes"][idx].sum(1)[:, None]
    vb = 100 * sb["viol"][idx].sum(1) / sb["notes"][idx].sum(1)[:, None]
    dd = va.max(1) - vb.max(1)
    out["D"] = {"delta": float((100 * sa["viol"].sum(0) / sa["notes"].sum()).max()
                               - (100 * sb["viol"].sum(0) / sb["notes"].sum()).max()),
                "ci95": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))]}
    return out


def table(S: dict, order: list[str]) -> str:
    h = ("| System | D (worst check) | 95% CI | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | "
         "Rhythmic indep. | Doubling | Note ratio |\n|" + "---|" * 11 + "\n")
    for sy in order:
        if sy not in S:
            continue
        r = S[sy]
        f, t = r["fidelity"], r["texture"]
        h += (f"| {sy} | {r['D']:.3f} ({r['D_check']}) | [{r['D_ci95'][0]:.3f}, {r['D_ci95'][1]:.3f}] | "
              f"{f['note_i_f1']:.3f} | {f['note_f1']:.3f} | {f['mel_f1']:.3f} | {f['harmony']:.3f} | "
              f"{t['polyphony_rate']:.3f} | {t['rhythmic_independence']:.3f} | {t['doubling_rate']:.3f} | "
              f"{t['note_ratio__total']:.3f} |\n")
    any_r = next(iter(S.values()))["texture"]
    h += (f"| *source* | | | | | | | {any_r['polyphony_rate__source']:.3f} | "
          f"{any_r['rhythmic_independence__source']:.3f} | {any_r['doubling_rate__source']:.3f} | 1.000 |\n")
    return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="arranger-v1")
    ap.add_argument("--regimes", nargs="+", default=["trio", "duo"])
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    rd = ROOT / "model" / "results" / a.run
    for regime in a.regimes:
        paths = [str(p) for p in (rd / "records" / f"arranger__{regime}.jsonl",
                                  rd / "records" / f"arranger_masked__{regime}.jsonl") if p.exists()]
        paths += [str(REC / f"{s}__{regime}.jsonl") for s in
                  ("ou_band", "ou_band_masked", "ou_band_repair", "continuity", "naive", "amt")
                  if (REC / f"{s}__{regime}.jsonl").exists()]
        od = rd / "eval" / regime
        run(paths, od / "harness", workers=a.workers, soft=True)
        metrics: dict[str, list] = {}
        for line in open(od / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            metrics.setdefault(m["system"], []).append(m)
        amt = metrics.pop("amt", None)
        keys = sorted(set.intersection(*[{r["input_id"] for r in rs} for rs in metrics.values()]))
        idx = np.random.default_rng(SEED).integers(0, len(keys), (N_BOOT, len(keys)))
        S = summarise(metrics, keys, idx)
        res = {"metrics_version": METRICS_VERSION, "regime": regime, "n_movements": len(keys), "systems": S,
               "paired": {}}
        for model_sys in ("arranger_masked", "arranger"):
            if model_sys not in metrics:
                continue
            for ref in REFS:
                if ref in metrics:
                    res["paired"][f"{model_sys} - {ref}"] = deltas(metrics, keys, idx, model_sys, ref)
        if amt:
            ak = sorted({r["input_id"] for r in amt})
            aidx = np.random.default_rng(SEED).integers(0, len(ak), (N_BOOT, len(ak)))
            res["amt_secondary"] = summarise({"amt": amt}, ak, aidx)["amt"]
        (od / "eval.json").write_text(json.dumps(res, indent=1))
        order = ["arranger_masked", "arranger", "ou_band", "ou_band_masked", "ou_band_repair", "continuity", "naive"]
        md = f"## {regime} ({len(keys)} movements, METRICS {METRICS_VERSION})\n\n" + table(S, order)
        md += "\nPaired deltas (row system - reference), 95% CI:\n\n| Pair | Note_i F1 | Harmony | Note F1 | Mel F1 | D |\n|---|---|---|---|---|---|\n"
        for pair, d in res["paired"].items():
            md += f"| {pair} | " + " | ".join(f"{d[k]['delta']:+.3f} [{d[k]['ci95'][0]:+.3f}, {d[k]['ci95'][1]:+.3f}]"
                                            for k in ("note_i_f1", "harmony", "note_f1", "mel_f1", "D")) + " |\n"
        (od / "table.md").write_text(md)
        print(md, flush=True)


if __name__ == "__main__":
    main()
