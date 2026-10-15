"""Per-check violation rates. Never aggregated across check types."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from arrangement.checker.types import CHECKS, Violation


def rates_per_100(violations: Iterable[Violation], n_assigned: int) -> dict[str, dict[str, float]]:
    """Per check type: violations per 100 assigned notes, and distinct notes
    implicated per 100 assigned notes (a chord-size violation counts once but
    implicates every sounding note)."""
    vs = list(violations)
    count = Counter(v.check for v in vs)
    implicated: dict[str, set[int]] = {c: set() for c in CHECKS}
    for v in vs:
        implicated[v.check].update(v.note_ids)
    scale = 100.0 / n_assigned if n_assigned else 0.0
    return {c: {"violations": count[c], "violations_per_100": count[c] * scale,
                "notes_implicated_per_100": len(implicated[c]) * scale}
            for c in CHECKS}
