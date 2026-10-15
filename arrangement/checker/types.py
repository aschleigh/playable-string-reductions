"""Checker data types: the note arrays the checker reads, and its outputs."""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Literal, Sequence

import numpy as np

Check = Literal["simultaneity", "range", "chord_size", "hand_span", "transition",
                "multistop", "bow", "shift", "duplicate", "hand_leap",
                "triple_onset", "triple_stretch", "triple_rate",
                "double_onset", "restrike", "double_rate"]
CHECKS: tuple[Check, ...] = ("simultaneity", "range", "chord_size", "hand_span", "transition",
                             "multistop", "bow", "shift", "duplicate", "hand_leap",   # checker-v2
                             "triple_onset", "triple_stretch", "triple_rate",         # checker-v3
                             "double_onset", "restrike", "double_rate",               # checker-v4
                             "triple_recover")                                        # checker-v5

UNASSIGNED = -1


def _frac(x) -> Fraction:
    if isinstance(x, float):
        return Fraction(x).limit_denominator(10_000)
    return Fraction(x)


@dataclass(frozen=True, eq=False)
class NoteArrays:
    """Struct-of-arrays view of a movement's notes, in exact integer ticks.

    Note id == array index. `tpq` (ticks per quarter) is the LCM of every
    onset/duration denominator, so all time comparisons are exact.
    """
    onset: np.ndarray     # int64 ticks
    end: np.ndarray       # int64 ticks; == onset for grace notes
    pitch: np.ndarray     # int64 sounding MIDI
    grace: np.ndarray     # bool
    tpq: int

    def __len__(self) -> int:
        return len(self.pitch)

    @classmethod
    def from_notes(cls, onsets: Sequence, durations: Sequence, pitches: Sequence[int],
                   grace: Sequence[bool] | None = None) -> NoteArrays:
        on = [_frac(x) for x in onsets]
        du = [_frac(x) for x in durations]
        g = [False] * len(on) if grace is None else [bool(x) for x in grace]
        if not (len(on) == len(du) == len(pitches) == len(g)):
            raise ValueError("onsets, durations, pitches, grace must have equal length")
        for d, gr in zip(du, g):
            if d < 0 or (d == 0 and not gr) or (gr and d != 0):
                raise ValueError("duration must be > 0, or exactly 0 for grace notes")
        tpq = 1
        for x in on + du:
            tpq = math.lcm(tpq, x.denominator)
        onset = np.array([int(x * tpq) for x in on], dtype=np.int64)
        end = onset + np.array([int(x * tpq) for x in du], dtype=np.int64)
        return cls(onset=onset, end=end, pitch=np.asarray(pitches, dtype=np.int64),
                   grace=np.asarray(g, dtype=bool), tpq=tpq)


@dataclass(frozen=True, order=True)
class Violation:
    """One hard-tier violation, attributed to notes and a part.

    note_ids: sorted ascending, except transition = (previous, next).
    measured / limit: the quantity that broke the rule and its threshold
    (pitch vs range bound, chord size vs max, span vs reach, leap vs allowed,
    overlap in quarter notes vs 0).
    """
    check: Check
    part_id: int
    note_ids: tuple[int, ...]
    measured: float
    limit: float


@dataclass(frozen=True)
class Delta:
    """Change to the violation set caused by one commit/uncommit."""
    added: tuple[Violation, ...]
    removed: tuple[Violation, ...]


def canonical(vs: Iterable[Violation]) -> list[Violation]:
    """Deduplicated, deterministically ordered violation list."""
    return sorted(set(vs))
