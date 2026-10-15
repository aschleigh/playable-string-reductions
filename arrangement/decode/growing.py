"""A growing incremental checker, for decoding where notes are created on the fly.

GrowingChecker subclasses the frozen IncrementalChecker and only adds storage:
append() creates a new (unassigned) note slot, pop() removes the last slot if it
is unassigned. Every rule and every violation comes from the parent class code,
unchanged. Times are integer ticks at a fixed `tpq` chosen up front, and the
longest possible note (`max_dur_ticks`) must be known up front because the
parent's interval lookups use it as a search bound.

Tested against the batch checker in tests/test_decode_growing.py.
"""
from __future__ import annotations

import numpy as np

from arrangement.checker.incremental import IncrementalChecker
from arrangement.checker.types import UNASSIGNED, NoteArrays, Violation
from arrangement.instruments import Ensemble


class GrowingChecker(IncrementalChecker):
    def __init__(self, ensemble: Ensemble, tpq: int, max_dur_ticks: int, capacity: int = 1024):
        empty = NoteArrays(onset=np.zeros(0, np.int64), end=np.zeros(0, np.int64),
                           pitch=np.zeros(0, np.int64), grace=np.zeros(0, bool), tpq=tpq)
        super().__init__(empty, ensemble)
        self._maxdur = int(max_dur_ticks)
        self.assign = np.full(capacity, UNASSIGNED, dtype=np.int64)
        self.n = 0

    def append(self, onset: int, end: int, pitch: int, grace: bool = False) -> int:
        if end - onset > self._maxdur:
            raise ValueError("note longer than max_dur_ticks")
        if self.n == len(self.assign):
            self.assign = np.concatenate([self.assign, np.full(len(self.assign), UNASSIGNED, np.int64)])
        self._on.append(int(onset)); self._end.append(int(end))
        self._pitch.append(int(pitch)); self._grace.append(bool(grace))
        self.n += 1
        return self.n - 1

    def pop(self) -> None:
        i = self.n - 1
        if self.assign[i] != UNASSIGNED:
            raise ValueError("cannot pop a committed note")
        for lst in (self._on, self._end, self._pitch, self._grace):
            lst.pop()
        self.n -= 1

    def would_add(self, onset: int, end: int, pitch: int, part: int, grace: bool = False) -> tuple[Violation, ...]:
        """Violations that adding this note to `part` would create. State unchanged."""
        i = self.append(onset, end, pitch, grace)
        try:
            return self.would_violate(i, part)
        finally:
            self.pop()

    def add(self, onset: int, end: int, pitch: int, part: int, grace: bool = False) -> tuple[int, tuple[Violation, ...]]:
        i = self.append(onset, end, pitch, grace)
        return i, self.commit(i, part).added
