"""Score the gate (DECODING.md) with the frozen harness and apply the decision rule.

    python -m decoding.gate --regime trio [--workers N]

1. Arrangement records for the masked outputs (same conversion as
   headroom/to_records.py for neural systems).
2. The frozen harness (METRICS.md 1.0.0-draft) on ou_band_masked, ou_band,
   continuity and amt for the regime -> decoding/results/<regime>/harness/.
3. Pooled statistics + paired movement bootstrap -> decoding/results/<regime>/gate.json
"""
from __future__ import annotations

import argparse
import json
import zlib
from fractions import Fraction
from pathlib import Path

import numpy as np

from arrangement.checker import CHECKS
from arrangement.eval.harness import METRICS_VERSION, run
from arrangement.eval.record import ArrangementRecord, load, make_score, save
from arrangement.instruments import load_ensemble
from headroom.measure import PROGRAM_PART, REFERENCE

ROOT = Path(__file__).resolve().parents[1]
REC = ROOT / "headroom" / "data" / "records"
OUT = ROOT / "headroom" / "data" / "out"
RES = ROOT / "decoding" / "results"
N_BOOT, SEED, MARGIN, D_MAX = 10_000, 0, 0.02, 0.5
FID = ["note_i_f1", "note_f1", "mel_f1", "harmony"]


def base_system(regime: str) -> str:
    return "ou_piano" if regime == "piano" else "ou_band"


def masked_records(regime: str) -> Path:
    bs = base_system(regime)
    base = {r.input_id: r for r in load(REC / f"{bs}__{regime}.jsonl")}
    ens = load_ensemble(regime)
    parts = [(n, i.key) for n, i in zip(ens.part_names, ens.instruments)]
    m = PROGRAM_PART[regime]
    recs = []
    for f in sorted((OUT / f"{bs}_masked" / regime).glob("*.json")):
        g = json.loads(f.read_text())
        b = base[g["key"]]
        kept = [(m[int(p)], Fraction(o), Fraction(d), int(x)) for p, o, d, x in g["notes"] if int(p) in m]
        recs.append(ArrangementRecord(
            system=f"{bs}_masked", seed=g["seed"], input_id=g["key"], ensemble=regime,
            source=b.source, output=make_score(parts, kept), bars=b.bars,
            reference_source_parts=tuple(tuple(r) for r in REFERENCE[regime]),
            meta={**b.meta, "n_off_ensemble": len(g["notes"]) - len(kept), "masking": g["masking"]}))
    p = REC / f"{bs}_masked__{regime}.jsonl"
    save(recs, p)
    return p


def _stats(rows: list[dict]) -> dict:
    """rows: metric records of one system; arrays aligned by input_id order."""
    v = np.array([[r["playability"][f"{c}__violations"] for c in CHECKS] for r in rows], float)
    n = np.array([r["playability"]["n_notes"] for r in rows], float)
    f = {}
    for k in FID:
        if k == "harmony":
            s = np.array([r["fidelity"]["vs_source"]["harmony__sum"] for r in rows])
            c = np.array([r["fidelity"]["vs_source"]["harmony__n_beats"] for r in rows], float)
        else:
            s = np.array([r["fidelity"]["vs_source"][f"{k}__sum"] for r in rows])
            c = np.array([r["fidelity"]["vs_source"][f"{k}__n_segments"] for r in rows], float)
        f[k] = (s, c)
    return {"viol": v, "notes": n, "fid": f}


def analyse(metrics: dict[str, list[dict]], base: str = "ou_band") -> dict:
    keys = sorted(set.intersection(*[{r["input_id"] for r in rs} for rs in metrics.values()]))
    S = {sy: _stats(sorted([r for r in rs if r["input_id"] in keys], key=lambda r: r["input_id"]))
         for sy, rs in metrics.items()}
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(keys), (N_BOOT, len(keys)))
    out = {"n_movements": len(keys), "systems": {}}
    for sy, s in S.items():
        rates = 100 * s["viol"].sum(0) / s["notes"].sum()
        bv = 100 * s["viol"][idx].sum(1) / s["notes"][idx].sum(1)[:, None]
        D = bv.max(1)
        row = {"D": float(rates.max()), "D_check": CHECKS[int(rates.argmax())],
               "D_ci95": [float(np.percentile(D, 2.5)), float(np.percentile(D, 97.5))],
               "per_100": dict(zip(CHECKS, map(float, rates))), "n_notes": int(s["notes"].sum()), "fidelity": {}}
        for k, (sm, c) in s["fid"].items():
            row["fidelity"][k] = float(sm.sum() / c.sum())
        out["systems"][sy] = row
    # paired fidelity deltas: unconstrained - masked
    a, b = S[base], S[f"{base}_masked"]
    out["delta_unconstrained_minus_masked"] = {}
    for k in FID:
        (sa, ca), (sb, cb) = a["fid"][k], b["fid"][k]
        point = sa.sum() / ca.sum() - sb.sum() / cb.sum()
        boot = sa[idx].sum(1) / ca[idx].sum(1) - sb[idx].sum(1) / cb[idx].sum(1)
        out["delta_unconstrained_minus_masked"][k] = {
            "delta": float(point), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
    out["note_ratio_masked_vs_unconstrained"] = float(b["notes"].sum() / a["notes"].sum())
    # decision rule
    D_hi = out["systems"][f"{base}_masked"]["D_ci95"][1]
    d = out["delta_unconstrained_minus_masked"]
    prim = [d["note_i_f1"]["ci95"], d["harmony"]["ci95"]]
    if D_hi > D_MAX:
        verdict = "blocking failed to reach low violations: diagnose"
    elif all(ci[1] < MARGIN for ci in prim):
        verdict = "outcome 1: blocking is enough; stop and talk"
    elif any(ci[0] > MARGIN for ci in prim):
        verdict = "outcome 2 or 3: training has a target; proceed"
    else:
        verdict = "undecided on fidelity: outcome 1 not established; proceed, flagged"
    out["verdict"] = verdict
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regime", default="trio")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--res", default=str(RES), help="results root (checker-v2 runs: decoding/results/v2)")
    a = ap.parse_args(argv)
    bs = base_system(a.regime)
    res_root = Path(a.res)
    # every baseline that exists for the regime is scored; only masked vs unconstrained is paired
    paths = [str(masked_records(a.regime))] + [str(REC / f"{s}__{a.regime}.jsonl")
                                               for s in (bs, f"{bs}_repair", "continuity", "naive", "control", "amt")
                                               if (REC / f"{s}__{a.regime}.jsonl").exists()]
    hd = res_root / a.regime / "harness"
    run(paths, hd, workers=a.workers, soft=True)
    metrics: dict[str, list] = {}
    for line in open(hd / "metrics.jsonl"):
        m = json.loads(line)
        metrics.setdefault(m["system"], []).append(m)
    amt = metrics.pop("amt", None)
    res = analyse(metrics, bs)
    res["metrics_version"] = METRICS_VERSION
    if amt:   # secondary, 32-bar window: reported separately, not paired
        res["amt_secondary"] = analyse({bs: metrics[bs], f"{bs}_masked": metrics[f"{bs}_masked"],
                                        "amt": amt}, bs)["systems"]["amt"]
    (res_root / a.regime / "gate.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
