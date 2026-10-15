"""One interface for every score format. Each backend turns a file into the
same ParsedPiece (arrangement.parse): sounding MIDI pitch, onsets/durations in
quarter notes, tie chains merged, percussion excluded, part identity from
declared parts -- or, where a format cannot declare parts, flagged
part_inferred so it is never mistaken for ground truth."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from arrangement.parse import ParsedPiece


class Backend(Protocol):
    name: str
    suffixes: tuple[str, ...]

    def n_movements(self, path: str | Path) -> int: ...

    def read(self, path: str | Path, movement: int | None = None) -> ParsedPiece: ...
