"""MusicXML (.xml/.musicxml/.mxl): the ground-truth path. Wraps
arrangement.parse, which reads the declared <score-part>s."""
from __future__ import annotations

from pathlib import Path

from arrangement.parse import ParsedPiece, load_raw_score, movement_index_ranges, parse_score


class MusicXMLBackend:
    name = "musicxml"
    suffixes = (".xml", ".musicxml", ".mxl")

    def __init__(self, expand_repeats: bool = True):
        self.expand_repeats = expand_repeats

    def n_movements(self, path: str | Path) -> int:
        return len(movement_index_ranges(load_raw_score(path)))

    def read(self, path: str | Path, movement: int | None = None, score=None) -> ParsedPiece:
        return parse_score(path, expand_repeats=self.expand_repeats, movement=movement, score=score)
