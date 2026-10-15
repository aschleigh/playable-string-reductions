"""Checker timing on real movements, single process (python tests/bench_corpus.py).
Needs the corpus cache. The 25 largest movements plus a random sample of 75; best of 5."""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from arrangement.assign import naive  # noqa: E402
from arrangement.checker import check  # noqa: E402
from arrangement.corpus import ROOT, load_cached, manifest  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402
from arrangement.strip import strip_labels  # noqa: E402


def best(fn, reps=5):
    out = float("inf")
    for _ in range(reps):
        t = time.perf_counter(); fn(); out = min(out, time.perf_counter() - t)
    return out


def main():
    ens = load_ensemble("quartet")
    rows = sorted((r for r in manifest() if r["status"] == "ok"), key=lambda r: -r["n_notes"])
    sample = rows[:25] + random.Random(0).sample(rows[25:], 75)
    res = []
    for r in sample:
        up, t = strip_labels(load_cached(r["key"]))
        notes = up.arrays()
        nv = naive(notes, ens)
        res.append((len(up), 1e3 * best(lambda: check(notes, ens, t.part_id)), 1e3 * best(lambda: check(notes, ens, nv))))
    a = np.array(res)
    out = {}
    for name, sel in (("largest_25", slice(0, 25)), ("random_75", slice(25, None))):
        x = a[sel]
        out[name] = {"notes_median": int(np.median(x[:, 0])), "notes_max": int(x[:, 0].max()),
                     "floor_ms_median": round(float(np.median(x[:, 1])), 2), "floor_ms_max": round(float(x[:, 1].max()), 2),
                     "naive_ms_median": round(float(np.median(x[:, 2])), 2), "naive_ms_max": round(float(x[:, 2].max()), 2),
                     "over_10ms_floor": int((x[:, 1] > 10).sum()), "over_10ms_naive": int((x[:, 2] > 10).sum())}
    us_per_note = a[:, 1] / a[:, 0] * 1e3
    out["floor_us_per_note_median"] = round(float(np.median(us_per_note)), 3)
    print(json.dumps(out, indent=1))
    (ROOT / "results" / "validation" / "checker_timing.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
