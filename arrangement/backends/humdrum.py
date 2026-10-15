"""Humdrum **kern: interface only (approved decision 9). No kern data in the
project corpus; implement read() when a kern corpus is added."""
from __future__ import annotations

from pathlib import Path

from arrangement.parse import ParsedPiece


class HumdrumBackend:
    name = "humdrum"
    suffixes = (".krn",)

    def n_movements(self, path: str | Path) -> int:
        raise NotImplementedError("Humdrum backend is a stub (PLAN.md decision 9)")

    def read(self, path: str | Path, movement: int | None = None) -> ParsedPiece:
        raise NotImplementedError("Humdrum backend is a stub (PLAN.md decision 9)")
