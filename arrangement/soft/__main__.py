"""Recompute only the soft section for a records file, under a given config.

    python -m arrangement.soft RECORDS.jsonl [...] [--config X.yaml] --out DIR

Writes DIR/soft.jsonl and DIR/soft.csv; every row carries soft_version and
config_sha1, so runs under different thresholds can be told apart and joined
to the harness output by record_id.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from arrangement.eval.playability import ensemble_of
from arrangement.eval.record import load
from arrangement.soft import load_config, soft_cost


def _flat(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{prefix}{k}."))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                out.update(_flat(x, f"{prefix}{k}.{i}.") if isinstance(x, dict) else {f"{prefix}{k}.{i}": x})
        else:
            out[f"{prefix}{k}"] = v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("records", nargs="+")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    rows = []
    for path in a.records:
        for r in load(path):
            rows.append({"record_id": r.record_id, "system": r.system, "seed": r.seed, "input_id": r.input_id,
                         "ensemble": r.ensemble, "soft": soft_cost(r.output, ensemble_of(r.output), cfg)})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "soft.jsonl", "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    flat = [_flat(r) for r in rows]
    cols = list(dict.fromkeys(k for r in flat for k in r))
    with open(out / "soft.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(flat)
    print(json.dumps({"n_records": len(rows), "config": a.config or "default",
                      "config_sha1": rows[0]["soft"]["config_sha1"] if rows else None}))


if __name__ == "__main__":
    main()
