"""Tune the continuity assigner's weights for LABEL ACCURACY on a fixed dev
split (movements with crc32(key) % 10 == 0). The checker is never called.

    python -m arrangement.tune_assigner [--workers N]            # grid on dev split
    python -m arrangement.tune_assigner --heldout [--workers N]  # configured weights, other 90%

Writes results/assigner/tuning.json; the chosen weights must then be copied
into config/assigner.yaml by hand (the config stays the single source).
"""
from __future__ import annotations

import argparse
import json
import time
import zlib
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from arrangement.assign import ContinuityParams, continuity, naive
from arrangement.corpus import CACHE, ROOT, load_cached, manifest
from arrangement.instruments import load_ensemble
from arrangement.strip import strip_labels

OUT = ROOT / "results" / "assigner"
# (crossing, w_cont, w_busy). "allow" grid = the earlier search's best region.
GRID = ([("forbid", wc, wb) for wc in [1.0, 2.0, 4.0, 8.0, 16.0, 32.0] for wb in [16.0, 64.0, 256.0, 1024.0, 4096.0]]
        + [("allow", wc, wb) for wc in [0.0, 0.5, 2.0] for wb in [64.0, 256.0]])


def is_dev(key: str) -> bool:
    return zlib.crc32(key.encode()) % 10 == 0


def ok_keys(cache: Path = CACHE) -> list[str]:
    return sorted(r["key"] for r in manifest(cache) if r["status"] == "ok")


def _score(key: str, grid: list[tuple[str, float, float]]) -> dict:
    ens = load_ensemble("quartet")
    up, target = strip_labels(load_cached(key))
    notes = up.arrays()
    y = target.part_id
    out = {"key": key, "n": int(len(y)), "naive": int((naive(notes, ens) == y).sum())}
    for cr, wc, wb in grid:
        out[f"{cr},{wc},{wb}"] = int((continuity(notes, ens, ContinuityParams(1.0, wc, wb, cr)) == y).sum())
    return out


def _heldout(key: str) -> tuple:
    ens = load_ensemble("quartet")
    up, target = strip_labels(load_cached(key))
    notes, y = up.arrays(), target.part_id
    t0 = time.perf_counter()
    c = continuity(notes, ens)                       # configured weights
    dt = time.perf_counter() - t0
    allow = continuity(notes, ens, ContinuityParams(1.0, 0.0, 64.0, "allow"))   # best "allow" on dev
    return len(y), int((naive(notes, ens) == y).sum()), int((c == y).sum()), int((allow == y).sum()), dt


def heldout(workers: int) -> dict:
    keys = [k for k in ok_keys() if not is_dev(k)]
    with Pool(workers) as pool:
        rows = pool.map(_heldout, keys)
    n = sum(r[0] for r in rows)
    out = {"heldout_movements": len(keys), "notes": n, "naive": sum(r[1] for r in rows) / n,
           "continuity_configured": sum(r[2] for r in rows) / n,
           "continuity_allow_best_dev": sum(r[3] for r in rows) / n,
           "continuity_ms_per_1000_notes": 1e6 * sum(r[4] for r in rows) / n}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "heldout_accuracy.json").write_text(json.dumps(out, indent=1))
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--heldout", action="store_true")
    args = ap.parse_args(argv)
    if args.heldout:
        print(json.dumps(heldout(args.workers), indent=1))
        return
    keys = [k for k in ok_keys() if is_dev(k)]
    grid = GRID
    with Pool(args.workers) as pool:
        rows = pool.map(partial(_score, grid=grid), keys)
    n = sum(r["n"] for r in rows)
    acc = {f"{cr},{wc},{wb}": sum(r[f"{cr},{wc},{wb}"] for r in rows) / n for cr, wc, wb in grid}
    best = max(acc, key=lambda k: (acc[k], k))
    best_allow = max((k for k in acc if k.startswith("allow")), key=lambda k: (acc[k], k))
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"dev_movements": keys, "n_notes": n, "naive_accuracy": sum(r["naive"] for r in rows) / n,
              "w_band": 1.0, "grid_accuracy": acc,
              "best": {"crossing": best.split(",")[0], "w_cont": float(best.split(",")[1]),
                       "w_busy": float(best.split(",")[2]), "accuracy": acc[best]},
              "best_crossing_allowed": {"key": best_allow, "accuracy": acc[best_allow]}}
    (OUT / "tuning.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k not in ("dev_movements", "grid_accuracy")}, indent=1))
    for k in sorted(acc, key=lambda k: -acc[k])[:12]:
        print(f"{acc[k]:.4f}  {k}")


if __name__ == "__main__":
    main()
