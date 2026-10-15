"""Step 4 validation: the checker on real scores.

    python -m arrangement.validate [--workers N]

floor    : true part assignment of every cached OpenScore movement. Should
           pass; every violation is triaged (results/validation/TRIAGE.md).
ceiling  : naive assigner on the same movements.
also     : continuity assigner, for reference.

Outputs (results/validation/):
  summary.json          pooled per-check rates per 100 notes, per-movement
                        distribution, concentration, checker timing
  per_movement.csv      one row per movement x assignment
  floor_violations.jsonl  every floor violation with score context
  README.md             the report (tables generated from summary.json and
                        checker_timing.json, written by tests/bench_corpus.py)
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.assign import continuity, naive
from arrangement.checker import CHECKS, check
from arrangement.corpus import ROOT, load_cached
from arrangement.instruments import load_ensemble
from arrangement.strip import strip_labels
from arrangement.tune_assigner import ok_keys

OUT = ROOT / "results" / "validation"
ASSIGNMENTS = ("floor", "naive", "continuity")


def _context(key, up, target, v) -> dict:
    notes = [up.notes[i] for i in v.note_ids]
    return {"key": key, "check": v.check, "part": target.part_names[v.part_id], "part_id": v.part_id,
            "note_ids": list(v.note_ids), "original_ids": [int(target.original_id[i]) for i in v.note_ids],
            "measured": v.measured, "limit": v.limit,
            "measure": notes[-1].measure, "onset": notes[-1].onset,
            "notes": [{"onset": n.onset, "duration": n.duration, "pitch": n.pitch, "grace": n.is_grace,
                       "measure": n.measure} for n in notes]}


def _run(key: str) -> dict:
    ens = load_ensemble("quartet")
    up, target = strip_labels(load_cached(key))
    notes = up.arrays()
    out = {"key": key, "n_notes": len(up), "counts": {}, "check_ms": None, "floor_violations": []}
    for name in ASSIGNMENTS:
        a = target.part_id if name == "floor" else (naive(notes, ens) if name == "naive" else continuity(notes, ens))
        vs = check(notes, ens, a)
        out["counts"][name] = dict(Counter(v.check for v in vs))
        if name == "floor":
            reps = []
            for _ in range(5):
                t0 = time.perf_counter()
                check(notes, ens, a)
                reps.append(time.perf_counter() - t0)
            out["check_ms"] = 1e3 * min(reps)
            out["floor_violations"] = [_context(key, up, target, v) for v in vs]
    return out


def _dist(rates: np.ndarray) -> dict:
    return {"movements_with_any": int((rates > 0).sum()), "mean": float(rates.mean()),
            "median": float(np.median(rates)), "p90": float(np.quantile(rates, 0.9)),
            "p99": float(np.quantile(rates, 0.99)), "max": float(rates.max())}


def summarize(rows: list[dict]) -> dict:
    N = sum(r["n_notes"] for r in rows)
    n = np.array([r["n_notes"] for r in rows], dtype=float)
    summary: dict = {"movements": len(rows), "notes": int(N)}
    for name in ASSIGNMENTS:
        s = {}
        for c in CHECKS:
            cnt = np.array([r["counts"][name].get(c, 0) for r in rows], dtype=float)
            rates = 100 * cnt / n
            order = np.argsort(-cnt)
            top5 = max(1, int(round(0.05 * len(rows))))
            s[c] = {"violations": int(cnt.sum()), "per_100_notes": float(100 * cnt.sum() / N),
                    "per_movement_rate": _dist(rates),
                    "share_of_violations_in_top_5pct_movements": float(cnt[order[:top5]].sum() / cnt.sum()) if cnt.sum() else None,
                    "worst_movements": [{"key": rows[i]["key"], "violations": int(cnt[i]), "per_100": float(rates[i])}
                                        for i in order[:5] if cnt[i] > 0]}
        summary[name] = s
    ms = np.array([r["check_ms"] for r in rows])
    summary["checker_ms_floor"] = {"median": float(np.median(ms)), "p99": float(np.quantile(ms, 0.99)),
                                   "max": float(ms.max()), "movements_over_10ms": int((ms > 10).sum()),
                                   "max_notes": int(n.max()),
                                   "notes_of_slowest": int(n[int(np.argmax(ms))])}
    return summary


# Rates under the first configuration (release-based 24-semitone transition cap,
# placeholder upper ranges, no harmonic/unison handling, before the cue fix);
# kept for the record of what the decisions changed.
FIRST_RUN = {"floor": {"range": 0.0048, "chord_size": 0.0003, "transition": 0.0389},
             "naive": {"range": 0.0014, "chord_size": 0.3318, "transition": 0.0155}}


def write_readme(summary: dict, timing: dict | None) -> str:
    s = summary
    CH = list(CHECKS)
    fl, nv = s["floor"], s["naive"]
    L = ["# Step 4: checker validation on real scores", "",
         f"{s['movements']} OpenScore string-quartet movements, {s['notes']:,} notes, config of",
         "`arrangement/config/instruments.yaml` (thresholds: open-string lows and 4-string chords sourced;",
         "upper ranges and transitions CORPUS-CALIBRATED, see UNSOURCED.md). Violations per 100 assigned",
         "notes, one row per check type. No aggregate score.", "",
         "## Rates per 100 notes", "",
         "| Check | Floor (true parts) | Ceiling (naive) | Continuity | Floor, first run | Naive, first run |",
         "|---|---|---|---|---|---|"]
    for c in CH:
        L.append(f"| {c} | {fl[c]['per_100_notes']:.4f} | {nv[c]['per_100_notes']:.4f} | "
                 f"{s['continuity'][c]['per_100_notes']:.4f} | {FIRST_RUN['floor'].get(c, 0):.4f} | "
                 f"{FIRST_RUN['naive'].get(c, 0):.4f} |")
    L += ["", "Simultaneity and hand span are 0 by construction for strings (not monophonic; no keyboard).",
          "\"First run\" = before the parser fixes and the threshold decisions (PLAN.md decisions 3, 10-12).", "",
          "## Distribution across movements", "",
          "Per-movement rate per 100 notes. Top-5% share = fraction of that check's violations in the worst 5% of movements.", "",
          "| Assignment | Check | Violations | Movements with any | Median | p90 | p99 | Max | Top-5% share | Worst movements (count) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for name in ASSIGNMENTS:
        for c in ("range", "chord_size", "transition"):
            d = s[name][c]
            pm = d["per_movement_rate"]
            if not d["violations"]:
                L.append(f"| {name} | {c} | 0 | 0 | | | | | | |")
                continue
            worst = "; ".join(f"{w['key'].split('__')[0].split(',')[0]} {w['key'].split('__')[1][:26]} "
                              f"{w['key'][-3:]} ({w['violations']})" for w in d["worst_movements"][:3])
            L.append(f"| {name} | {c} | {d['violations']} | {pm['movements_with_any']} | {pm['median']:.3f} | "
                     f"{pm['p90']:.3f} | {pm['p99']:.3f} | {pm['max']:.3f} | "
                     f"{d['share_of_violations_in_top_5pct_movements']:.0%} | {worst} |")
    n_floor = sum(fl[c]["violations"] for c in CH)
    L += ["", "Full per-movement counts: `per_movement.csv`. Floor triage: `TRIAGE.md`.", "",
          "## Reading it", "",
          f"1. **Floor:** {n_floor} violations, none a parser bug (TRIAGE.md). Transition violations are real",
          "   leaps just beyond the envelope fitted on the 10% dev split, all in held-out movements. That is",
          "   the one independent test of the calibration, and it shows the dev split underestimates the tail.",
          "   Range-high is calibrated on the full corpus, so passing it is not evidence.",
          f"2. **Ceiling:** naive fails chord size ({nv['chord_size']['per_100_notes']:.2f} per 100 notes, in "
          f"{nv['chord_size']['per_movement_rate']['movements_with_any']} movements) and almost nothing else.",
          "   An envelope wide enough to pass real quartet writing never trips on naive's pitch-banded lines",
          "   (naive transitions: " + f"{nv['transition']['violations']}" + "). For string quartet, the hard tier",
          "   rejects over-full chords and little else: it is a floor, not a discriminator.",
          f"3. **Continuity** has no chord-size violations, but range {s['continuity']['range']['per_100_notes']:.2f}"
          " per 100 notes: spreading pushes low notes into upper parts when the cello is busy, and the checker catches it.",
          ""]
    if timing:
        L += ["## Checker speed on real movements (single process, best of 5; `tests/bench_corpus.py`)", "",
              "| Sample | Median notes | Floor ms (median / max) | Naive ms (median / max) | Movements > 10 ms |",
              "|---|---|---|---|---|"]
        for k, label in (("largest_25", "25 largest movements"), ("random_75", "75 random movements")):
            t = timing[k]
            L.append(f"| {label} | {t['notes_median']} | {t['floor_ms_median']} / {t['floor_ms_max']} | "
                     f"{t['naive_ms_median']} / {t['naive_ms_max']} | {t['over_10ms_floor'] + t['over_10ms_naive']} |")
        L += ["", "`checker_ms_floor` in summary.json is measured under 48 parallel workers and overstates this.", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    keys = ok_keys()
    with Pool(args.workers) as pool:
        rows = sorted(pool.map(_run, keys, chunksize=1), key=lambda r: r["key"])
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "floor_violations.jsonl").open("w") as fh:
        for r in rows:
            for v in r["floor_violations"]:
                fh.write(json.dumps(v, ensure_ascii=False) + "\n")
    with (out_dir / "per_movement.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "assignment", "n_notes"] + list(CHECKS) + ["check_ms"])
        for r in rows:
            for name in ASSIGNMENTS:
                w.writerow([r["key"], name, r["n_notes"]] + [r["counts"][name].get(c, 0) for c in CHECKS]
                           + [round(r["check_ms"], 3) if name == "floor" else ""])
    summary = summarize(rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    timing_path = out_dir / "checker_timing.json"
    timing = json.loads(timing_path.read_text()) if timing_path.exists() else None
    (out_dir / "README.md").write_text(write_readme(summary, timing))
    for name in ASSIGNMENTS:
        print(name, {c: round(summary[name][c]["per_100_notes"], 4) for c in CHECKS})
    print("checker", summary["checker_ms_floor"])


if __name__ == "__main__":
    main()
