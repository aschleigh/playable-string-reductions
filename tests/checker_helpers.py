"""Shared helpers for checker tests."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from arrangement.checker import NoteArrays
from arrangement.instruments import load_ensemble, load_instruments

GOLDEN = Path(__file__).resolve().parent / "golden"


def ensemble(name: str, time_basis: str | None = None):
    """name: "quartet" (real config) or "test" (golden fixture config). time_basis
    overrides every instrument's transition.time_basis."""
    if name == "quartet":
        ens = load_ensemble("quartet")
    else:
        ens = load_ensemble(GOLDEN / "test_ensemble.yaml", load_instruments(GOLDEN / "instruments_test.yaml"))
    if time_basis is None:
        return ens
    insts = tuple(replace(i, transition=replace(i.transition, time_basis=time_basis)) if i.transition else i
                  for i in ens.instruments)
    return replace(ens, instruments=insts)


def build(notes: list[tuple]) -> tuple[NoteArrays, np.ndarray]:
    on = [n[0] for n in notes]
    du = [n[1] for n in notes]
    pi = [n[2] for n in notes]
    gr = [bool(n[4]) if len(n) > 4 else False for n in notes]
    return NoteArrays.from_notes(on, du, pi, gr), np.array([n[3] for n in notes], dtype=np.int64)
