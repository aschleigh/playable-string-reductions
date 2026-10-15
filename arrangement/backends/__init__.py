"""Format dispatch: load(path) picks the backend by file suffix."""
from __future__ import annotations

from pathlib import Path

from arrangement.backends.base import Backend
from arrangement.backends.humdrum import HumdrumBackend
from arrangement.backends.midi import MidiBackend
from arrangement.backends.musicxml import MusicXMLBackend
from arrangement.parse import ParsedPiece

BACKENDS: tuple[Backend, ...] = (MusicXMLBackend(), MidiBackend(), HumdrumBackend())


def backend_for(path: str | Path) -> Backend:
    suffix = Path(path).suffix.lower()
    for b in BACKENDS:
        if suffix in b.suffixes:
            return b
    raise ValueError(f"no backend for {suffix!r} ({path})")


def load(path: str | Path, movement: int | None = None) -> ParsedPiece:
    return backend_for(path).read(path, movement=movement)


__all__ = ["Backend", "BACKENDS", "backend_for", "load", "MusicXMLBackend", "MidiBackend", "HumdrumBackend"]
