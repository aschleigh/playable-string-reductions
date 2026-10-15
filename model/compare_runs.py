"""Step 3 report: arranger-v2 against arranger-v1, same frozen harness (METRICS 1.3.0-draft, checker-v4).

    python -m model.compare_runs --a arranger-v2 --b arranger-v1 [--workers 16]

Per regime (trio, duo) and mode (plain, masked):
  - every pooled harness metric of both runs, and paired deltas (a - b) with 95% movement
    bootstrap CIs (decoding.gate / model.evaluate statistics, unchanged);
  - intervention rate (masked; decode diag `masked_interventions`, or the Step 1 diagnostic
    value for v1, whose diag predates the counter);
  - per-tier retention (top / inner / bass, BLOCK4.md 2b tier rule) and the unneeded
    double-stop rate (BLOCK4.md 2b definition: an onset in an output part with >= 2 sounding
    notes whose pitches do not all sound together in one source part at that time), both
    computed from the records. These are the METRICS 1.4.0 candidates, reported here as
    diagnostics, not as harness fields.
Writes model/results/<a>/compare_<b>.json and .md.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from fractions import Fraction as F
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.eval.record import load
from model.diagnose import voice_tiers
from model.evaluate import deltas, summarise

ROOT = Path(__file__).resolve().parents[1]
V1_INTERVENTIONS = {"trio": 0.1185, "duo": 0.2216}   # BLOCK4.md 1c (instrumented re-decode of v1)
KEYS = ["note_i_f1", "note_f1", "mel_f1", "harmony"]


def unneeded_double_stops(out_notes, src_notes):
    """(events, unneeded events) over output-part onsets with >= 2 sounding notes."""
    src_by_part = defaultdict(list)
    for p, o, d, x in src_notes:
        src_by_part[p].append((o, o + d, x))

    def supported(t, pitches):
        for ns in src_by_part.values():
            snd = {x for a, b, x in ns if a <= t < b}
            if pitches <= snd:
                return True
        return False
    per_part = defaultdict(list)
    for p, o, d, x in out_notes:
        if d > 0:
            per_part[p].append((o, o + d, x))
    ev = un = 0
    for ns in per_part.values():
        ns.sort()
        active, k = [], 0
        for t in sorted({n[0] for n in ns}):
            while k < len(ns) and ns[k][0] <= t:
                active.append(ns[k]); k += 1
            active = [n for n in active if n[1] > t]
            if len(active) >= 2:
                ev += 1
                un += not supported(t, {n[2] for n in active})
    return ev, un


def _rec_job(r):
    src = sorted(r.source.notes, key=lambda n: (n[1], n[3], n[2]))
    tiers = voice_tiers(src)
    by = defaultdict(list)
    for _, o, d, x in r.output.notes:
        by[x].append(o)
    kept, n = Counter(), Counter()
    for (sp, o, d, x), t in zip(src, tiers):
        n[t] += 1; n[f"src{sp}"] += 1
        if any(abs(o - y) < F(1, 4) for y in by.get(x, ())):
            kept[t] += 1; kept[f"src{sp}"] += 1
    ev, un = unneeded_double_stops(r.output.notes, r.source.notes)
    return r.input_id, kept, n, ev, un, len(r.output.notes), len(src)


def record_diagnostics(path, workers):
    with Pool(workers) as pool:
        rows = pool.map(_rec_job, load(path), chunksize=2)
    kept, n, ev, un, no, ns = Counter(), Counter(), 0, 0, 0, 0
    for _, k_, n_, e, u, a, b in rows:
        kept.update(k_); n.update(n_); ev += e; un += u; no += a; ns += b
    names = ["Vn1", "Vn2", "Va", "Vc"]
    return {"retention": {t: kept[t] / n[t] for t in ("top", "inner", "bass")},
            "retention_by_source_part": {names[s]: kept[f"src{s}"] / n[f"src{s}"] for s in range(4)},
            "double_stop_events_per_100_out": 100 * ev / no,
            "unneeded_double_stops_per_100_out": 100 * un / no,
            "unneeded_double_stops_per_source_note": un / ns}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="arranger-v2")
    ap.add_argument("--b", default="arranger-v1")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    RA, RB = ROOT / "model" / "results" / a.a, ROOT / "model" / "results" / a.b
    res, md = {}, [f"# {a.a} vs {a.b} (checker-v4, METRICS 1.3.0-draft; 150 evaluation movements)\n"]
    for regime in ("trio", "duo"):
        M = defaultdict(list)
        for run, tag in ((RA, "A"), (RB, "B")):
            for line in open(run / "eval" / regime / "harness" / "metrics.jsonl"):
                m = json.loads(line)
                if m["system"] in ("arranger", "arranger_masked"):
                    M[f"{m['system']}@{tag}"].append(m)
        keys = sorted(set.intersection(*[{r["input_id"] for r in rs} for rs in M.values()]))
        idx = np.random.default_rng(0).integers(0, len(keys), (10_000, len(keys)))
        S = summarise(M, keys, idx)
        R = {"n_movements": len(keys), "systems": S, "paired": {}, "diagnostics": {}}
        for sy in ("arranger", "arranger_masked"):
            R["paired"][sy] = deltas(M, keys, idx, f"{sy}@A", f"{sy}@B")
            for run, tag in ((RA, "A"), (RB, "B")):
                R["diagnostics"][f"{sy}@{tag}"] = record_diagnostics(run / "records" / f"{sy}__{regime}.jsonl", a.workers)
        diag = json.loads((RA / "records" / f"arranger_masked__{regime}.diag.json").read_text())
        R["intervention_rate"] = {"A": sum(d["masked_interventions"] for d in diag) / sum(d["n_in"] for d in diag),
                                  "B": V1_INTERVENTIONS[regime]}
        R["drop_rate_masked"] = {"A": sum(d["n_drop"] for d in diag) / sum(d["n_in"] for d in diag)}
        res[regime] = R
        md.append(f"\n## {regime}\n\n| System | D | Note_i F1 | Note F1 | Mel F1 | Harmony | Polyphony | Rhythmic ind. | "
                  f"Doubling | Note ratio | Retention top / inner / bass | Unneeded double stops per 100 notes |\n"
                  + "|" + "---|" * 12 + "\n")
        for sy in ("arranger_masked", "arranger"):
            for tag, name in (("B", a.b), ("A", a.a)):
                r, dg = S[f"{sy}@{tag}"], R["diagnostics"][f"{sy}@{tag}"]
                f, t = r["fidelity"], r["texture"]
                md.append(f"| {name} {sy.replace('arranger', '').strip('_') or 'plain'} | {r['D']:.2f} | {f['note_i_f1']:.3f} | "
                          f"{f['note_f1']:.3f} | {f['mel_f1']:.3f} | {f['harmony']:.3f} | {t['polyphony_rate']:.3f} | "
                          f"{t['rhythmic_independence']:.3f} | {t['doubling_rate']:.3f} | {t['note_ratio__total']:.3f} | "
                          f"{dg['retention']['top']:.3f} / {dg['retention']['inner']:.3f} / {dg['retention']['bass']:.3f} | "
                          f"{dg['unneeded_double_stops_per_100_out']:.1f} |\n")
        md.append(f"\nIntervention rate (masked): {a.b} {R['intervention_rate']['B']:.3f}, {a.a} {R['intervention_rate']['A']:.3f}.\n"
                  f"\nPaired deltas ({a.a} − {a.b}), 95% CI:\n\n| Mode | Note_i F1 | Note F1 | Mel F1 | Harmony | D |\n|---|---|---|---|---|---|\n")
        for sy, d in R["paired"].items():
            md.append(f"| {sy} | " + " | ".join(f"{d[k]['delta']:+.3f} [{d[k]['ci95'][0]:+.3f}, {d[k]['ci95'][1]:+.3f}]"
                                                for k in KEYS + ["D"]) + " |\n")
    (RA / f"compare_{a.b}.json").write_text(json.dumps(res, indent=1))
    (RA / f"compare_{a.b}.md").write_text("".join(md))
    print("".join(md))


if __name__ == "__main__":
    main()
