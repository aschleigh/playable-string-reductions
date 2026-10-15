"""Soft tier (PROVISIONAL): per-instrument playing COSTS, never violations.

    soft_cost(score, ens, config=None) -> dict

Thresholds live in arrangement/config/soft.yaml (or a path / dict passed as
`config`). A cost type applies to a part when its block is present under the
part's instrument key. Returned per cost type: summed cost, event count and
cost per 100 notes (of the parts it applies to), plus the same per part.
Cost types are never summed with each other.

Shared conventions (README.md): grace notes (duration 0) are ignored; times
are quarter notes; "_seconds" thresholds use assumed_qpm. The melodic line
for shift / crossing is the highest note at each onset of the part.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

SOFT_VERSION = "0.1.0-provisional"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "soft.yaml"
COST_TYPES = ("breath", "bow", "shift", "crossing", "register", "key", "repeated")
BLACK_KEYS = {1, 3, 6, 8, 10}


def load_config(config: str | Path | dict | None = None) -> dict:
    if config is None:
        config = DEFAULT_CONFIG
    if isinstance(config, dict):
        return copy.deepcopy(config)
    return yaml.safe_load(Path(config).read_text())


def config_sha1(cfg: dict) -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


# ------------------------------------------------------------ per-part costs
# Each takes the part's non-grace notes as (onset, duration, pitch) floats,
# sorted by (onset, pitch), and returns (cost, events).

def _top_line(notes):
    top: dict[float, float] = {}
    for o, _, x in notes:
        top[o] = max(top.get(o, x), x)
    return sorted(top.items())


def breath(notes, c, qpm):
    if not notes:
        return 0.0, 0
    sec = 60.0 / qpm
    cost, events = 0.0, 0
    start, end = notes[0][0], notes[0][0] + notes[0][1]
    for o, d, _ in notes[1:] + [(float("inf"), 0.0, 0)]:
        if o - end >= c["min_breath_gap"]:
            excess = (end - start) * sec - c["max_phrase_seconds"]
            if excess > 0:
                cost += excess; events += 1
            start, end = o, o + d
        else:
            end = max(end, o + d)
    return cost, events


def bow(notes, c, qpm):
    sec = 60.0 / qpm
    ex = [d * sec - c["max_bow_seconds"] for _, d, _ in notes]
    ex = [e for e in ex if e > 0]
    return float(sum(ex)), len(ex)


def shift(notes, c, qpm):
    line = _top_line(notes)
    cost, events = 0.0, 0
    for (t0, p0), (t1, p1) in zip(line, line[1:]):
        jump = abs(p1 - p0)
        if jump > c["frame_semitones"] and t1 - t0 <= c["max_shift_ioi"]:
            cost += jump - c["frame_semitones"]; events += 1
    return cost, events


def string_of(pitch, open_strings) -> int:
    k = 0
    for i, s in enumerate(open_strings):
        if s <= pitch:
            k = i
    return k


def crossing(notes, c, qpm, open_strings):
    line = _top_line(notes)
    cost, events = 0.0, 0
    for (t0, p0), (t1, p1) in zip(line, line[1:]):
        k = abs(string_of(p1, open_strings) - string_of(p0, open_strings))
        e = max(0, k - 1) + (1 if k >= 1 and t1 - t0 < c["fast_ioi"] else 0)
        if e:
            cost += e; events += 1
    return cost, events


def register(notes, c, qpm):
    ex = [x - c["comfortable_high"] for _, _, x in notes if x > c["comfortable_high"]]
    return float(sum(ex)), len(ex)


def key(notes, transposition):
    n = sum(1 for _, _, x in notes if (x + transposition) % 12 in BLACK_KEYS)
    return float(n), n


def repeated(notes, c, qpm):
    last: dict[float, float] = {}
    cost, events = 0.0, 0
    for o, _, x in notes:
        if x in last and o > last[x]:
            ioi = o - last[x]
            if ioi < c["min_ioi"]:
                cost += (c["min_ioi"] - ioi) / c["min_ioi"]; events += 1
        last[x] = o
    return cost, events


def _part_costs(notes, ic: dict, qpm: float) -> dict[str, tuple[float, int] | None]:
    out: dict[str, tuple[float, int] | None] = {t: None for t in COST_TYPES}
    for t in ("breath", "bow", "shift", "register", "repeated"):
        if ic.get(t) is not None:
            out[t] = globals()[t](notes, ic[t], qpm)
    if ic.get("crossing") is not None:
        out["crossing"] = crossing(notes, ic["crossing"], qpm, ic["open_strings"])
    if ic.get("transposition"):
        out["key"] = key(notes, int(ic["transposition"]))
    return out


# ------------------------------------------------------------ entry point

def soft_cost(score, ens, config: str | Path | dict | None = None) -> dict[str, Any]:
    cfg = load_config(config)
    qpm = float(cfg["assumed_qpm"])
    icfg = cfg.get("instruments", {})
    parts = defaultdict(list)
    for p, o, d, x in score.notes:
        if d > 0:
            parts[p].append((float(o), float(d), int(x)))
    res: dict[str, Any] = {"soft_version": SOFT_VERSION, "config_sha1": config_sha1(cfg), "assumed_qpm": qpm,
                           "unconfigured_instruments": sorted({i.key for i in ens.instruments if i.key not in icfg})}
    per = []
    for p, inst in enumerate(ens.instruments):
        notes = sorted(parts.get(p, []), key=lambda n: (n[0], n[2]))
        per.append((len(notes), _part_costs(notes, icfg.get(inst.key, {}), qpm)))
    for t in COST_TYPES:
        rows, cost, events, n = [], 0.0, 0, 0
        for n_p, pc in per:
            v = pc[t]
            if v is None:
                rows.append(None)
                continue
            rows.append({"cost": v[0], "events": v[1], "per_100": 100.0 * v[0] / n_p if n_p else 0.0})
            cost += v[0]; events += v[1]; n += n_p
        applies = any(r is not None for r in rows)
        res[f"{t}__applies"] = applies
        res[f"{t}__cost"] = cost if applies else None
        res[f"{t}__events"] = events if applies else None
        res[f"{t}__per_100"] = (100.0 * cost / n if n else 0.0) if applies else None
        res[f"{t}__per_part"] = rows
    return res
