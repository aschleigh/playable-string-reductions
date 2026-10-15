"""The arrangement record: the one input contract of the evaluation harness.

Every system (rule-based assigner, constrained decoding, trained model, an
external system such as Ou et al.) emits one record per (input, seed). The
harness reads nothing else. Spec: METRICS.md, section "Arrangement record".

Times are exact quarter-note fractions, serialized as strings ("3/2").
A note is [part, onset, duration, pitch]: part = index into the part list of
the score it belongs to, pitch = sounding MIDI. Duration 0 = grace note.

Assigners place SOURCE notes, generators write NEW notes, so the output is
always given as notes in its own right. `assignment` is optional provenance:
assignment[i] = output part of source note i (-1 = dropped). When present it
must agree with the output notes exactly (validate()).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

RECORD_VERSION = "1"

Note = tuple[int, Fraction, Fraction, int]   # (part, onset, duration, pitch)


@dataclass(frozen=True)
class PartDecl:
    name: str
    instrument: str          # key in arrangement/config/instruments.yaml, or "" if none applies


@dataclass(frozen=True)
class Score:
    parts: tuple[PartDecl, ...]
    notes: tuple[Note, ...]   # sorted by (onset, pitch, part, duration)

    def __post_init__(self):
        for p, o, d, x in self.notes:
            if not 0 <= p < len(self.parts):
                raise ValueError(f"note part {p} outside 0..{len(self.parts) - 1}")
            if d < 0 or o < 0:
                raise ValueError("onset and duration must be >= 0")
            if not 0 <= x <= 127:
                raise ValueError(f"pitch {x} outside MIDI range")

    @property
    def instruments(self) -> tuple[str, ...]:
        return tuple(p.instrument for p in self.parts)


@dataclass(frozen=True)
class ArrangementRecord:
    system: str                    # system identifier, e.g. "naive", "ou_band", "rl-v3"
    seed: int | None               # None for deterministic systems
    input_id: str                  # identifies the source; records with one input_id share one source
    ensemble: str                  # ensemble name (config/ensembles/<name>.yaml or ad hoc)
    source: Score
    output: Score                  # parts = the target ensemble, in part-index order
    bars: tuple[tuple[Fraction, Fraction], ...]   # (start, length) of each source bar = Ou et al. segments
    assignment: tuple[int, ...] | None = None
    reference: Score | None = None   # a human arrangement for the same ensemble, if one exists
    reference_source_parts: tuple[tuple[int, ...], ...] | None = None  # per output part: source parts it reduces
    window: tuple[Fraction, Fraction] | None = None   # (start, end) if the system covered only part of the source
    system_version: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.output.parts:
            raise ValueError("output needs at least one part")
        # A reference may have a different instrument count: fidelity matches by instrument
        # (METRICS.md), and the mismatch shows up as I-IoU < 1.
        if self.reference_source_parts is not None:
            if len(self.reference_source_parts) != len(self.output.parts):
                raise ValueError("reference_source_parts needs one entry per output part")
            for ref in self.reference_source_parts:
                if any(not 0 <= s < len(self.source.parts) for s in ref):
                    raise ValueError("reference_source_parts names a missing source part")
        if self.assignment is not None:
            if len(self.assignment) != len(self.source.notes):
                raise ValueError("assignment needs one entry per source note")
            implied = sorted((a, o, d, x) for a, (_, o, d, x) in zip(self.assignment, self.source.notes) if a >= 0)
            if implied != sorted(self.output.notes):
                raise ValueError("assignment does not reproduce the output notes")
        if not self.bars:
            raise ValueError("bars (the source bar timeline) are required")

    @property
    def record_id(self) -> str:
        return hashlib.sha1(json.dumps(to_json(self), sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- JSON

def _q(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def _score_json(s: Score) -> dict:
    return {"parts": [{"name": p.name, "instrument": p.instrument} for p in s.parts],
            "notes": [[p, _q(o), _q(d), x] for p, o, d, x in s.notes]}


def _score(d: dict) -> Score:
    notes = [(int(p), Fraction(o), Fraction(du), int(x)) for p, o, du, x in d["notes"]]
    notes.sort(key=lambda n: (n[1], n[3], n[0], n[2]))
    return Score(tuple(PartDecl(p["name"], p.get("instrument", "")) for p in d["parts"]), tuple(notes))


def make_score(parts: list[tuple[str, str]], notes: list) -> Score:
    """parts = [(name, instrument)], notes = [(part, onset, duration, pitch)] with any numeric times."""
    return _score({"parts": [{"name": n, "instrument": i} for n, i in parts],
                   "notes": [[p, str(Fraction(o)), str(Fraction(d)), x] for p, o, d, x in notes]})


def to_json(r: ArrangementRecord) -> dict:
    return {"record_version": RECORD_VERSION, "system": r.system, "system_version": r.system_version,
            "seed": r.seed, "input_id": r.input_id, "ensemble": r.ensemble,
            "source": _score_json(r.source), "output": _score_json(r.output),
            "bars": [[_q(a), _q(b)] for a, b in r.bars],
            "assignment": None if r.assignment is None else list(r.assignment),
            "reference": None if r.reference is None else _score_json(r.reference),
            "reference_source_parts": None if r.reference_source_parts is None
            else [list(x) for x in r.reference_source_parts],
            "window": None if r.window is None else [_q(r.window[0]), _q(r.window[1])],
            "meta": r.meta}


def from_json(d: dict) -> ArrangementRecord:
    if str(d.get("record_version")) != RECORD_VERSION:
        raise ValueError(f"record_version {d.get('record_version')!r}, harness reads {RECORD_VERSION!r}")
    r = ArrangementRecord(
        system=d["system"], system_version=d.get("system_version", ""), seed=d.get("seed"),
        input_id=d["input_id"], ensemble=d["ensemble"], source=_score(d["source"]), output=_score(d["output"]),
        bars=tuple((Fraction(a), Fraction(b)) for a, b in d["bars"]),
        assignment=None if d.get("assignment") is None else tuple(int(a) for a in d["assignment"]),
        reference=None if d.get("reference") is None else _score(d["reference"]),
        reference_source_parts=None if d.get("reference_source_parts") is None
        else tuple(tuple(int(s) for s in x) for x in d["reference_source_parts"]),
        window=None if d.get("window") is None else (Fraction(d["window"][0]), Fraction(d["window"][1])),
        meta=d.get("meta", {}))
    r.validate()
    return r


def save(records: list[ArrangementRecord], path: str | Path) -> None:
    """JSON Lines, one record per line."""
    with open(path, "w") as f:
        for r in records:
            r.validate()
            f.write(json.dumps(to_json(r)) + "\n")


def load(path: str | Path) -> list[ArrangementRecord]:
    with open(path) as f:
        return [from_json(json.loads(line)) for line in f if line.strip()]
