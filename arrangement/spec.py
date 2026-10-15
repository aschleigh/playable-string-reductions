"""Ensemble spec extraction: read the ensemble off a parsed score.

For each part: which instrument (matched by name against the config's
`names` patterns), its observed pitch range, its observed max simultaneity
(most non-grace notes sounding at one instant), and note count. The observed
values describe the score, not the instrument's physical limits (those live in
config/instruments.yaml).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from arrangement.instruments import Ensemble, InstrumentDef
from arrangement.parse import DeclaredPart, ParsedPiece


@dataclass(frozen=True)
class PartSpec:
    part_id: int
    name: str
    instrument: str | None        # config key, or None if unmatched/ambiguous
    n_notes: int
    low: int | None               # observed sounding pitch range (None if no notes)
    high: int | None
    max_simultaneity: int         # most non-grace notes sounding at one instant
    declared: bool                # False = part inferred (MIDI without instrument)


@dataclass(frozen=True)
class EnsembleSpec:
    source: str
    movement: int | None
    parts: tuple[PartSpec, ...]
    max_simultaneity: int         # across the whole ensemble

    @property
    def n_parts(self) -> int:
        return len(self.parts)


def identify_instrument(part: DeclaredPart, instruments: dict[str, InstrumentDef]) -> str | None:
    """First of (part name, instrument name) that matches exactly one instrument."""
    for text in (part.name, part.instrument_name):
        if not text:
            continue
        hits = [k for k, inst in instruments.items()
                if any(re.search(pat, text, re.IGNORECASE) for pat in inst.names)]
        if len(hits) == 1:
            return hits[0]
    return None


def max_simultaneity(onsets: np.ndarray, ends: np.ndarray) -> int:
    """Max number of half-open intervals [onset, end) covering one instant."""
    if not len(onsets):
        return 0
    on, en = np.sort(onsets), np.sort(ends)
    return int((np.searchsorted(on, on, side="right") - np.searchsorted(en, on, side="right")).max())


def extract_spec(piece: ParsedPiece, instruments: dict[str, InstrumentDef]) -> EnsembleSpec:
    on = np.array([e.onset for e in piece.events])
    en = np.array([e.end for e in piece.events])
    pid = np.array([e.part_id for e in piece.events], dtype=int)
    pitch = np.array([e.pitch for e in piece.events], dtype=int)
    ng = ~np.array([e.is_grace for e in piece.events], dtype=bool)
    parts = []
    for part in piece.parts:
        m = pid == part.part_id
        parts.append(PartSpec(
            part_id=part.part_id, name=part.name, instrument=identify_instrument(part, instruments),
            n_notes=int(m.sum()),
            low=int(pitch[m].min()) if m.any() else None, high=int(pitch[m].max()) if m.any() else None,
            max_simultaneity=max_simultaneity(on[m & ng], en[m & ng]), declared=part.declared))
    return EnsembleSpec(source=piece.source, movement=piece.movement, parts=tuple(parts),
                        max_simultaneity=max_simultaneity(on[ng], en[ng]) if len(on) else 0)


def to_ensemble(spec: EnsembleSpec, instruments: dict[str, InstrumentDef], name: str = "") -> Ensemble:
    """Checker ensemble for this score's parts, in part order."""
    missing = [p.name for p in spec.parts if p.instrument is None]
    if missing:
        raise ValueError(f"unidentified instruments for parts {missing}")
    return Ensemble(name=name or spec.source, part_names=tuple(p.name for p in spec.parts),
                    instruments=tuple(instruments[p.instrument] for p in spec.parts))
