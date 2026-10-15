"""Check every system's output with the frozen checker (tag checker-v1.1) and
apply the pre-registered decision rule (DECISION.md, amendment A1).
Runs in the CHECKER environment.

    python -m headroom.measure [--workers N]

Writes headroom/results/:
  per_score.csv     one row per (system, regime, movement): note counts,
                    per-part retention, per-check violations, generation
                    diagnostics -- the raw per-score data
  summary.json      pooled per-check rates, D, bootstrap CIs, per-score
                    distributions, retention, validity flags, verdicts
"""
from __future__ import annotations

import argparse
import csv
import json
import zlib
from collections import Counter
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.assign import continuity, naive
from arrangement.checker import CHECKS, check
from arrangement.checker.types import NoteArrays
from arrangement.instruments import load_ensemble

HEAD = Path(__file__).resolve().parent
SRC = HEAD / "data" / "sources"
OUT = HEAD / "data" / "out"
RES = HEAD / "results"

REGIMES = ["quartet", "trio", "duo", "solo_violin", "solo_flute", "piano"]
TIGHTNESS = ["quartet", "trio", "duo", "solo_violin", "solo_flute"]          # piano: separate keyboard point
BASELINE = "trio"
PRIMARY = {"trio": "ou_band", "duo": "ou_band", "solo_violin": "ou_band", "solo_flute": "ou_band", "piano": "ou_piano"}
# program -> part index per regime (neural outputs)
PROGRAM_PART = {"trio": {40: 0, 41: 1, 42: 2}, "duo": {40: 0, 42: 1}, "solo_violin": {40: 0},
                "solo_flute": {73: 0}, "piano": {0: 0}}
# reference source part(s) per target part, for retention (A1.6). Source parts: 0 Vn1, 1 Vn2, 2 Va, 3 Vc
REFERENCE = {"quartet": [[0], [1], [2], [3]], "trio": [[0], [2], [3]], "duo": [[0], [3]], "solo_violin": [[0]],
             "solo_flute": [[0]], "piano": [[0, 1, 2, 3]]}
AMT_BARS = 32
N_BOOT, BOOT_SEED = 10_000, 0
LOW, HIGH, CONTROL_MIN, RETENTION_MIN = 1.0, 5.0, 5.0, 0.8


def _arrays(notes: list[tuple[Fraction, Fraction, int]]) -> NoteArrays:
    return NoteArrays.from_notes([n[0] for n in notes], [n[1] for n in notes], [n[2] for n in notes])


def _row(system, regime, rec, ens, notes, assign, src_counts, extra) -> dict:
    vs = check(_arrays(notes), ens, np.asarray(assign, dtype=np.int64)) if notes else []
    cnt = Counter(v.check for v in vs)
    by_part = Counter(f"{v.check}:{v.part_id}" for v in vs)
    range_dir = Counter(f"{'below' if v.measured < v.limit else 'above'}:{v.part_id}" for v in vs if v.check == "range")
    per_part = Counter(int(a) for a in assign)
    refs = [sum(src_counts.get(p, 0) for p in ref) for ref in REFERENCE[regime]]
    retention = [per_part.get(k, 0) / r if r else None for k, r in enumerate(refs)]
    row = {"system": system, "regime": regime, "idx": rec["idx"], "key": rec["key"],
           "n_source_notes": sum(src_counts.values()), "n_out_notes": len(notes),
           "out_per_part": json.dumps([per_part.get(k, 0) for k in range(len(ens))]),
           "ref_per_part": json.dumps(refs),
           "min_part_retention": min(r for r in retention if r is not None),
           **{c: cnt.get(c, 0) for c in CHECKS},
           "by_check_part": json.dumps(dict(sorted(by_part.items()))),
           "range_direction": json.dumps(dict(sorted(range_dir.items()))), **extra}
    return row


def _src_window(rec, max_q=None):
    notes = [(int(p), Fraction(o), Fraction(d), int(x)) for p, o, d, x in rec["notes"]]
    if max_q is not None:
        notes = [n for n in notes if n[1] < max_q]
    notes.sort(key=lambda n: (n[1], n[3], n[2], n[0]))
    return notes


def score_movement(path: Path) -> list[dict]:
    rec = json.loads(path.read_text())
    src = _src_window(rec)
    src_counts = Counter(n[0] for n in src)
    plain = [(n[1], n[2], n[3]) for n in src]
    rows = []
    for regime in REGIMES:
        ens = load_ensemble(regime)
        P = len(ens)
        arr = _arrays(plain)
        if regime == "quartet":
            rows.append(_row("floor", regime, rec, ens, plain, [n[0] for n in src], src_counts, {}))
        rows.append(_row("naive", regime, rec, ens, plain, naive(arr, ens), src_counts, {}))
        if P > 1:   # the frozen continuity assigner raises for 1-part ensembles (_splits); not fixed (measure only)
            rows.append(_row("continuity", regime, rec, ens, plain, continuity(arr, ens), src_counts, {}))
        rng = np.random.default_rng(zlib.crc32(f"{rec['key']}|control|{regime}".encode()))
        rows.append(_row("control", regime, rec, ens, plain, rng.integers(0, P, len(plain)), src_counts, {}))
    for system, regime in [(PRIMARY[r], r) for r in PRIMARY] + [("amt", "trio")]:
        f = OUT / system / regime / path.name
        if not f.exists():
            continue
        out = json.loads(f.read_text())
        ens = load_ensemble(regime)
        m = PROGRAM_PART[regime]
        kept = [(Fraction(o), Fraction(d), int(x), m[int(prog)]) for prog, o, d, x in out["notes"] if int(prog) in m]
        kept.sort(key=lambda n: (n[0], n[2], n[1], n[3]))
        extra = {"n_off_ensemble": len(out["notes"]) - len(kept),
                 "bars_truncated": out.get("bars_truncated_at_max_length", ""),
                 "bars_unparseable": out.get("bars_unparseable", ""), "gen_seconds": round(out["seconds"], 1)}
        counts = src_counts
        if system == "amt":   # compare against the same 32-bar window of the source
            counts = Counter(n[0] for n in _src_window(rec, Fraction(out["end_q"])))
            extra["n_control_notes"] = out["n_control_notes"]
        rows.append(_row(system, regime, rec, ens, [k[:3] for k in kept], [k[3] for k in kept], counts, extra))
        # SENSITIVITY ONLY (not pre-registered, never decides): exact duplicates (same part, onset, pitch)
        # collapsed to one note, keeping the longest. REMI-z keeps duplicate tokens the model emits.
        best: dict = {}
        for k in kept:
            key = (k[3], k[0], k[2])
            if key not in best or k[1] > best[key][1]:
                best[key] = k
        dd = sorted(best.values(), key=lambda n: (n[0], n[2], n[1], n[3]))
        rows.append(_row(f"{system}_dedup", regime, rec, ens, [k[:3] for k in dd], [k[3] for k in dd], counts,
                         {**extra, "n_duplicates_removed": len(kept) - len(dd)}))
    return rows


def _pooled(c: np.ndarray, n: np.ndarray) -> np.ndarray:
    return 100.0 * c.sum(axis=-2) / n.sum(axis=-1)[..., None]


def summarize_group(rows: list[dict]) -> dict:
    c = np.array([[r[k] for k in CHECKS] for r in rows], dtype=float)       # scores x checks
    n = np.array([r["n_out_notes"] for r in rows], dtype=float)
    rates = _pooled(c, n)
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(rows), (N_BOOT, len(rows)))
    b = 100.0 * c[idx].sum(axis=1) / n[idx].sum(axis=1)[:, None]            # boot x checks
    D_boot = b.max(axis=1)
    per = 100.0 * c / np.maximum(n, 1)[:, None]
    out = {"n_scores": len(rows), "n_out_notes": int(n.sum()),
           "n_source_notes": int(sum(r["n_source_notes"] for r in rows)),
           "D": float(rates.max()), "D_check": CHECKS[int(rates.argmax())],
           "D_ci95": [float(np.percentile(D_boot, 2.5)), float(np.percentile(D_boot, 97.5))], "checks": {}}
    for k, ch in enumerate(CHECKS):
        order = np.argsort(-c[:, k])
        top = max(1, int(round(0.05 * len(rows))))
        out["checks"][ch] = {
            "violations": int(c[:, k].sum()), "per_100": float(rates[k]),
            "ci95": [float(np.percentile(b[:, k], 2.5)), float(np.percentile(b[:, k], 97.5))],
            "per_score": {"median": float(np.median(per[:, k])), "p90": float(np.percentile(per[:, k], 90)),
                          "max": float(per[:, k].max()), "scores_with_any": int((c[:, k] > 0).sum())},
            "top5pct_share": float(c[order[:top], k].sum() / c[:, k].sum()) if c[:, k].sum() else None,
            "worst": [{"key": rows[i]["key"], "violations": int(c[i, k]), "per_100": float(per[i, k])}
                      for i in order[:3] if c[i, k] > 0]}
    bcp, rdir = Counter(), Counter()
    for r in rows:
        bcp.update(json.loads(r["by_check_part"]))
        rdir.update(json.loads(r["range_direction"]))
    out["violations_by_check_part"] = dict(sorted(bcp.items()))
    out["range_by_direction_part"] = dict(sorted(rdir.items()))
    out_pp = np.array([json.loads(r["out_per_part"]) for r in rows], dtype=float).sum(axis=0)
    ref_pp = np.array([json.loads(r["ref_per_part"]) for r in rows], dtype=float).sum(axis=0)
    out["retention_per_part"] = (out_pp / np.maximum(ref_pp, 1)).round(4).tolist()
    out["retention_total_vs_source"] = round(float(n.sum() / max(1, sum(r["n_source_notes"] for r in rows))), 4)
    out["sparse"] = bool(min(out["retention_per_part"]) < RETENTION_MIN)
    out["sparse_original_rule"] = out["retention_total_vs_source"] < 0.8
    if "n_off_ensemble" in rows[0]:
        out["n_off_ensemble"] = int(sum(r["n_off_ensemble"] or 0 for r in rows))
        tr = [r["bars_truncated"] for r in rows if r["bars_truncated"] != ""]
        out["bars_truncated"] = int(sum(tr)) if tr else None
    return out


def band(ci: list[float]) -> str:
    lo, hi = ci
    if lo > HIGH:
        return "Proceed"
    if lo >= LOW and hi <= HIGH:
        return "Tighten"
    if hi < LOW:
        return "Pivot"
    return "Undecided"


def verdict(S: dict, regime: str) -> dict:
    sysname = PRIMARY.get(regime)
    if sysname is None or sysname not in S.get(regime, {}):
        return {"verdict": "no primary system for this regime"}
    s = S[regime][sysname]
    ctrl = S[regime]["control"]
    control_ok = ctrl["D_ci95"][0] > CONTROL_MIN
    raw = band(s["D_ci95"])
    v = raw
    notes = []
    if raw == "Pivot" and not control_ok:
        v, _ = "Uninformative: checker insensitive", notes.append("control CI not entirely above 5")
    if raw == "Pivot" and s["sparse"]:
        v, _ = "Sparsity, not playability", notes.append("a target part retains < 80% of its reference notes")
    return {"system": sysname, "D": s["D"], "D_check": s["D_check"], "D_ci95": s["D_ci95"],
            "band": raw, "verdict": v, "control_D_ci95": ctrl["D_ci95"], "control_valid": control_ok,
            "sparse": s["sparse"], "notes": notes}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--out", default=None, help="results dir (checker-v2 re-measurement: headroom/results_v2)")
    ap.add_argument("--checker-tag", default="checker-v1.1")
    a = ap.parse_args(argv)
    res = Path(a.out) if a.out else RES
    files = sorted(SRC.glob("*.json"))
    with Pool(a.workers) as pool:
        rows = [r for rs in pool.map(score_movement, files, chunksize=1) for r in rs]
    res.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (res / "per_score.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    S: dict = {}
    for regime in REGIMES:
        for system in sorted({r["system"] for r in rows if r["regime"] == regime}):
            g = [r for r in rows if r["regime"] == regime and r["system"] == system]
            S.setdefault(regime, {})[system] = summarize_group(g)
    complete = {f"{s}/{r}": len([x for x in rows if x["system"] == s and x["regime"] == r])
                for r in PRIMARY for s in [PRIMARY[r]]} | {"amt/trio": len([x for x in rows if x["system"] == "amt"])}
    summary = {"checker_tag": a.checker_tag, "n_movements": len(files), "outputs_present": complete,
               "summary": S, "baseline": verdict(S, BASELINE),
               "sweep": {r: verdict(S, r) for r in PRIMARY}}
    (res / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps({"outputs_present": complete, "baseline": summary["baseline"]}, indent=1))
    for r in REGIMES:
        for s, g in S[r].items():
            print(f"{r:12s} {s:11s} D={g['D']:8.3f} [{g['D_ci95'][0]:.3f}, {g['D_ci95'][1]:.3f}] {g['D_check']:12s}"
                  f" ret={min(g['retention_per_part']):.2f} total={g['retention_total_vs_source']:.2f}")


if __name__ == "__main__":
    main()
