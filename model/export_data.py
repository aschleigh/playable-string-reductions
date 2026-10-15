"""Export the model's train / validation movements (checker environment).

    python -m model.export_data

train = OpenScore movements that are neither in the headroom evaluation set
(headroom/data/eval_set.json, 150) nor in the dev split (crc32 % 10 == 0, 61);
val = the dev split. The evaluation set is never seen in training.
Writes model/data/{train,val}.jsonl: one movement per line,
{"key", "notes": [[part, onset, duration, pitch], ...]} (non-grace notes,
exact fractions as strings, parts Vn1 Vn2 Va Vc).
"""
from __future__ import annotations

import json
from pathlib import Path

from arrangement.corpus import load_cached, manifest
from arrangement.tune_assigner import is_dev

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model" / "data"


def _q(x) -> str:
    from fractions import Fraction
    f = Fraction(x).limit_denominator(10_000)
    return f"{f.numerator}/{f.denominator}"


def main():
    evalset = {r["key"] for r in json.loads((ROOT / "headroom" / "data" / "eval_set.json").read_text())}
    keys = sorted(r["key"] for r in manifest() if r["status"] == "ok")
    OUT.mkdir(parents=True, exist_ok=True)
    n = {"train": 0, "val": 0, "excluded_eval": 0}
    with open(OUT / "train.jsonl", "w") as tr, open(OUT / "val.jsonl", "w") as va:
        for k in keys:
            if k in evalset:
                n["excluded_eval"] += 1
                continue
            p = load_cached(k)
            notes = [[e.part_id, _q(e.onset), _q(e.duration), e.pitch] for e in p.events if not e.is_grace]
            split = "val" if is_dev(k) else "train"
            (va if split == "val" else tr).write(json.dumps({"key": k, "notes": notes}) + "\n")
            n[split] += 1
    (OUT / "split.json").write_text(json.dumps(n, indent=1))
    print(n)


if __name__ == "__main__":
    main()
