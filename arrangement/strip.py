"""Label stripper: remove part identity from a parsed piece, keeping it aside
as the assignment target.

Everything part-relative goes: part_id, voice_id, staff_id, tie_group_id
(numbered per part), and the event order itself -- parser ids come out
grouped by part, so notes are re-sorted by (onset, pitch, duration, grace)
and re-numbered. Exact duplicates (unisons between parts) are ordered by a
hash of (source, original id), which is deterministic but carries no part
order.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from arrangement.checker.types import NoteArrays
from arrangement.parse import ParsedPiece


@dataclass(frozen=True)
class UnlabeledNote:
    id: int
    onset: float
    duration: float
    pitch: int
    is_grace: bool
    is_tied: bool
    measure: int
    beat_strength: float

    @property
    def end(self) -> float:
        return self.onset + self.duration


@dataclass(frozen=True)
class UnlabeledPiece:
    source: str
    movement: int | None
    notes: tuple[UnlabeledNote, ...]
    total_duration: float

    def __len__(self) -> int:
        return len(self.notes)

    def arrays(self) -> NoteArrays:
        return NoteArrays.from_notes([n.onset for n in self.notes], [n.duration for n in self.notes],
                                     [n.pitch for n in self.notes], [n.is_grace for n in self.notes])


@dataclass(frozen=True)
class Target:
    """Held-out labels, aligned with UnlabeledPiece.notes by index."""
    part_id: np.ndarray          # int, the true part per note
    part_inferred: np.ndarray    # bool, True where the label is not ground truth
    original_id: np.ndarray      # int, the parser's event id
    part_names: tuple[str, ...]


def strip_labels(piece: ParsedPiece) -> tuple[UnlabeledPiece, Target]:
    def key(e):
        return (e.onset, e.pitch, e.duration, e.is_grace, zlib.crc32(f"{piece.source}:{e.id}".encode()))
    ordered = sorted(piece.events, key=key)
    notes = tuple(UnlabeledNote(id=k, onset=e.onset, duration=e.duration, pitch=e.pitch, is_grace=e.is_grace,
                                is_tied=e.is_tied, measure=e.measure, beat_strength=e.beat_strength)
                  for k, e in enumerate(ordered))
    target = Target(part_id=np.array([e.part_id for e in ordered], dtype=np.int64),
                    part_inferred=np.array([e.part_inferred for e in ordered], dtype=bool),
                    original_id=np.array([e.id for e in ordered], dtype=np.int64),
                    part_names=tuple(p.name for p in piece.parts))
    return UnlabeledPiece(piece.source, piece.movement, notes, piece.total_duration), target
