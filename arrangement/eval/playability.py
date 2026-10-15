"""Playability (hard tier) and the near-limit distribution. METRICS.md sections
"Playability" and "Texture and diversity" (near_limit).

Violations come from the frozen checker (arrangement.checker.check), unchanged.
The near-limit distribution needs the measured quantity at EVERY opportunity,
not only at violations. It is obtained from the same frozen code by checking
with each limit relaxed to "everything violates" (dataclasses.replace on the
instrument), so predecessor choice, sounding sets and hand splits are exactly
the checker's. Slack = limit - measured: < 0 is a violation, 0 sits on the limit.
"""
from __future__ import annotations

import dataclasses
from collections import Counter

import numpy as np

from arrangement.checker import CHECKS, check, rates_per_100
from arrangement.checker.batch import _part
from arrangement.checker.types import NoteArrays
from arrangement.eval.record import Score
from arrangement.instruments import Ensemble, InstrumentDef, Transition, load_instruments

_BIG = 1_000_000.0
SLACK_BINS = list(range(-5, 6))   # integer slack, clipped to [-5, 5]


def ensemble_of(score: Score, instruments: dict[str, InstrumentDef] | None = None) -> Ensemble:
    inst = instruments if instruments is not None else load_instruments()
    missing = [p.instrument for p in score.parts if p.instrument not in inst]
    if missing:
        raise ValueError(f"no instrument definition for {missing}")
    return Ensemble(name="", part_names=tuple(p.name for p in score.parts),
                    instruments=tuple(inst[p.instrument] for p in score.parts))


def arrays(score: Score) -> tuple[NoteArrays, np.ndarray]:
    n = score.notes
    na = NoteArrays.from_notes([x[1] for x in n], [x[2] for x in n], [x[3] for x in n], [x[2] == 0 for x in n])
    return na, np.array([x[0] for x in n], dtype=np.int64)


def violations(score: Score, ens: Ensemble):
    if not score.notes:
        return []
    na, part = arrays(score)
    return check(na, ens, part)


def playability(score: Score, ens: Ensemble) -> dict:
    vs = violations(score, ens)
    r = rates_per_100(vs, len(score.notes))
    out = {"n_notes": len(score.notes)}
    for c in CHECKS:
        out[f"{c}__violations"] = r[c]["violations"]
        out[f"{c}__per_100"] = r[c]["violations_per_100"] if score.notes else None
        out[f"{c}__implicated_per_100"] = r[c]["notes_implicated_per_100"] if score.notes else None
        out[f"{c}__applies"] = any(_applies(c, i) for i in ens.instruments)
    by_part = Counter(f"{v.check}:{v.part_id}" for v in vs)
    out["by_check_part"] = dict(sorted(by_part.items()))
    return out


def _applies(c: str, inst: InstrumentDef) -> bool:
    return {"simultaneity": inst.monophonic, "range": True, "chord_size": inst.max_chord is not None,
            "hand_span": inst.hand_span is not None, "transition": inst.transition is not None,
            "multistop": inst.strings is not None, "bow": inst.strings is not None, "shift": inst.strings is not None,
            "duplicate": not inst.monophonic and inst.strings is None,
            "hand_leap": inst.hand_leap is not None and inst.hand_span is not None,
            "triple_onset": inst.strings is not None and inst.strings.triple_max_stretch is not None,
            "triple_stretch": inst.strings is not None and inst.strings.triple_max_stretch is not None,
            "triple_rate": inst.strings is not None and inst.strings.triple_min_gap is not None,
            "double_onset": inst.strings is not None and inst.strings.double_min_gap is not None,
            "restrike": inst.strings is not None and inst.strings.double_min_gap is not None,
            "double_rate": inst.strings is not None and inst.strings.double_min_gap is not None,
            "triple_recover": inst.strings is not None and inst.strings.triple_recover is not None}[c]


# ------------------------------------------------------------ near-limit

def slacks(score: Score, ens: Ensemble) -> dict[str, list[float]]:
    """Slack at every opportunity, per check (pooled over parts)."""
    res: dict[str, list[float]] = {c: [] for c in CHECKS}
    if not score.notes:
        return res
    na, part = arrays(score)
    for p, inst in enumerate(ens.instruments):
        idx = np.flatnonzero(part == p)
        if not len(idx):
            continue
        pitch = na.pitch[idx]
        res["range"] += list(np.minimum(pitch - inst.low, inst.high - pitch).astype(float))
        if inst.max_chord is not None:
            relaxed = dataclasses.replace(inst, max_chord=0, hand_span=None, transition=None, low=0, high=127, strings=None, hand_leap=None)
            res["chord_size"] += [inst.max_chord - v.measured for v in _part(na, p, relaxed, idx)
                                  if v.check == "chord_size"]
        if inst.hand_span is not None:
            hs = dataclasses.replace(inst.hand_span, semitones=-1)
            relaxed = dataclasses.replace(inst, hand_span=hs, max_chord=None, transition=None, low=0, high=127, strings=None, hand_leap=None)
            res["hand_span"] += [inst.hand_span.semitones - v.measured for v in _part(na, p, relaxed, idx)
                                 if v.check == "hand_span"]
        if inst.transition is not None:
            t = inst.transition
            relaxed = dataclasses.replace(inst, transition=Transition(t.max_leap_at_zero_gap - _BIG,
                                                                      t.semitones_per_quarter_gap, t.time_basis),
                                          max_chord=None, hand_span=None, low=0, high=127, strings=None, hand_leap=None)
            res["transition"] += [(v.limit + _BIG) - v.measured for v in _part(na, p, relaxed, idx)
                                  if v.check == "transition"]
        if inst.monophonic:
            # gap from each non-grace note's release to the next onset in the part, in quarter notes
            ng = idx[~na.grace[idx]]
            ng = ng[np.lexsort((ng, na.onset[ng]))]
            if len(ng) > 1:
                res["simultaneity"] += list(((na.onset[ng[1:]] - na.end[ng[:-1]]) / na.tpq).astype(float))
    return res


def near_limit(score: Score, ens: Ensemble) -> dict:
    """Histogram of slack per check. Integer checks: bins -5..5 (clipped).
    Simultaneity: gap in 16th notes, bins -5..5 (clipped). Plus the share of
    opportunities sitting on or just inside the limit (0 <= slack <= 1 bin)."""
    out = {}
    for c, s in slacks(score, ens).items():
        a = np.asarray(s, dtype=float)
        if c == "simultaneity":
            a = a * 4
        a = np.clip(np.floor(a + 1e-9), SLACK_BINS[0], SLACK_BINS[-1]).astype(int) if len(a) else a
        hist = Counter(int(x) for x in a)
        out[f"{c}__n_opportunities"] = int(len(a))
        out[f"{c}__hist"] = {str(b): hist.get(b, 0) for b in SLACK_BINS}
        out[f"{c}__share_at_limit"] = float(np.mean((a >= 0) & (a <= 1))) if len(a) else None
        out[f"{c}__share_violating"] = float(np.mean(a < 0)) if len(a) else None
    return out
