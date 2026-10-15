"""Evaluation harness: arrangement records in, metric records out.

    python -m arrangement.eval.harness RECORDS.jsonl [...] --out DIR [--workers N] [--no-soft]

Writes to DIR:
  metrics.jsonl   one metric record per arrangement record (nested, complete)
  metrics.csv     the same, flattened to scalar columns (for joining runs)
  seeds.jsonl     one row per (system, ensemble, input_id): spread across seeds
  run.json        spec version, inputs, config hashes, counts
Every row carries `metrics_version` (METRICS.md) so runs stay comparable.
Playability, fidelity, texture and soft cost are separate sections; nothing
here combines them into one score.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.eval import fidelity, playability as play, reduction, texture as tex
from arrangement.eval.record import ArrangementRecord, Score, from_json
from arrangement.instruments import DEFAULT_INSTRUMENTS

METRICS_VERSION = "1.5.0-draft"   # bump per METRICS.md changelog


def windowed(r: ArrangementRecord):
    """Source, reference and bars restricted to the window the system covered."""
    if r.window is None:
        start, end = r.bars[0][0], r.bars[-1][0] + r.bars[-1][1]
        return r.source, r.reference, r.bars, start, end
    a, b = r.window
    keep = lambda s: None if s is None else Score(s.parts, tuple(n for n in s.notes if a <= n[1] < b))
    bars = tuple(x for x in r.bars if x[0] < b and x[0] + x[1] > a)
    return keep(r.source), keep(r.reference), bars, a, b


def evaluate(r: ArrangementRecord, soft: bool = True) -> dict:
    src, ref, bars, start, end = windowed(r)
    ens = play.ensemble_of(r.output)
    out = r.output
    m: dict = {"metrics_version": METRICS_VERSION, "record_id": r.record_id, "system": r.system,
               "system_version": r.system_version, "seed": r.seed, "input_id": r.input_id,
               "ensemble": r.ensemble, "instruments": list(out.instruments),
               "has_reference": ref is not None, "has_assignment": r.assignment is not None,
               "window": None if r.window is None else [str(start), str(end)],
               "n_source_notes": len(src.notes), "n_output_notes": len(out.notes), "n_segments": len(bars)}
    m["playability"] = play.playability(out, ens)
    m["fidelity"] = {"vs_source": {**fidelity.reference_metrics(out, src, bars),
                                   **fidelity.harmony_agreement(out, src, start, end)},
                     "vs_reference": None if ref is None else fidelity.reference_metrics(out, ref, bars)}
    m["texture"] = tex.texture(out, src, ens, end - start, r.reference_source_parts)
    m["near_limit"] = play.near_limit(out, ens)
    m["reduction"] = reduction.reduction_metrics(out, src)
    if soft:
        from arrangement.soft import soft_cost
        m["soft"] = soft_cost(out, ens)
    return m


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        elif isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                for i, x in enumerate(v):
                    out[f"{key}.{i}"] = x
            else:
                for i, x in enumerate(v):
                    if isinstance(x, dict):
                        out.update(_flatten(x, f"{key}.{i}."))
                    else:
                        out[f"{key}.{i}"] = x
        else:
            out[key] = v
    return out


def _scalar_paths(m: dict) -> dict[str, float]:
    """Numeric leaves of a metric record, for spread across seeds."""
    skip = ("seed", "n_segments", "__sum", "__n_", "__hist", "violations")
    return {k: float(v) for k, v in _flatten(m).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not any(s in k for s in skip)}


def _group_row(key, metrics: list[dict], pairwise: dict) -> dict:
    system, ens, inp = key
    row = {"metrics_version": METRICS_VERSION, "system": system, "ensemble": ens, "input_id": inp,
           "seeds": [m["seed"] for m in metrics], **pairwise}
    if len(metrics) < 2:          # spread is undefined for one seed; the values are in metrics.jsonl
        row["spread"] = None
        return row
    vals = defaultdict(list)
    for m in metrics:
        for k, v in _scalar_paths(m).items():
            vals[k].append(v)
    row["spread"] = {k: {"mean": float(np.mean(v)), "std": float(np.std(v, ddof=1))}
                     for k, v in sorted(vals.items()) if len(v) == len(metrics)}
    return row


def seed_groups(records: list[ArrangementRecord], metrics: list[dict]) -> list[dict]:
    """In-memory version (tests, small runs)."""
    groups = defaultdict(list)
    for r, m in zip(records, metrics):
        groups[(r.system, r.ensemble, r.input_id)].append((r, m))
    return [_group_row(k, [m for _, m in items],
                       tex.seed_pairwise([r.output for r, _ in items], windowed(items[0][0])[2]))
            for k, items in sorted(groups.items())]


def _read_lines(path: str, lines: list[int]) -> list[ArrangementRecord]:
    want, out = set(lines), {}
    with open(path) as f:
        for k, line in enumerate(f):
            if k in want:
                out[k] = from_json(json.loads(line))
    return [out[k] for k in lines]


def _eval_chunk(args) -> list[dict]:
    path, lines, soft = args
    res = []
    for k, r in zip(lines, _read_lines(path, lines)):
        m = evaluate(r, soft)
        m["_loc"] = (path, k)
        res.append(m)
    return res


def _pairwise_job(locs) -> dict:
    by_path = defaultdict(list)
    for p, k in locs:
        by_path[p].append(k)
    rs = [r for p, ks in by_path.items() for r in _read_lines(p, ks)]
    return tex.seed_pairwise([r.output for r in rs], windowed(rs[0])[2])


def _line_count(path: str) -> int:
    with open(path) as f:
        return sum(1 for line in f if line.strip())


def _json_default(o):
    if isinstance(o, Fraction):
        return str(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    raise TypeError(type(o))


def _clean(x):
    return None if isinstance(x, float) and math.isnan(x) else x


def run(paths: list[str], out_dir: str | Path, workers: int = 1, soft: bool = True, chunk: int = 4) -> dict:
    """Workers read and parse their own chunks of each records file, so nothing large passes
    through the parent. Seed groups with >= 2 records get a second parallel pass (pairwise F1)."""
    jobs = [(str(p), list(range(i, min(i + chunk, n))), soft)
            for p in paths for n in [_line_count(p)] for i in range(0, n, chunk)]
    with Pool(max(1, workers)) as pool:
        metrics = [m for ms in pool.imap(_eval_chunk, jobs) for m in ms]
        groups = defaultdict(list)
        for m in metrics:
            groups[(m["system"], m["ensemble"], m["input_id"])].append(m)
        keys = sorted(groups)
        multi = [k for k in keys if len(groups[k]) > 1]
        pw = dict(zip(multi, pool.map(_pairwise_job, [[m["_loc"] for m in groups[k]] for k in multi])))
    seeds = [_group_row(k, groups[k], pw.get(k, {"n_seeds": 1, "pairwise_note_f1": None,
                                                     "pairwise_note_i_f1": None})) for k in keys]
    for m in metrics:
        m.pop("_loc")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "metrics.jsonl", "w") as f:
        for m in metrics:
            f.write(json.dumps(m, default=_json_default) + "\n")
    flat = [_flatten(m) for m in metrics]
    cols = sorted({k for r in flat for k in r})
    lead = ["metrics_version", "record_id", "system", "system_version", "seed", "input_id", "ensemble"]
    cols = lead + [c for c in cols if c not in lead]
    with open(out / "metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in flat:
            w.writerow({k: _clean(v) for k, v in r.items()})
    with open(out / "seeds.jsonl", "w") as f:
        for s in seeds:
            f.write(json.dumps(s, default=_json_default) + "\n")
    cfg = {p.name: hashlib.sha1(p.read_bytes()).hexdigest()[:12]
           for p in sorted(Path(DEFAULT_INSTRUMENTS).parent.rglob("*.yaml"))}
    info = {"metrics_version": METRICS_VERSION, "inputs": paths, "n_records": len(metrics),
            "n_seed_groups": len(seeds), "soft": soft, "config_sha1": cfg}
    (out / "run.json").write_text(json.dumps(info, indent=1))
    return info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("records", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--no-soft", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(run(a.records, a.out, a.workers, not a.no_soft), indent=1))


if __name__ == "__main__":
    main()
