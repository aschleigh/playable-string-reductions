"""Tensorize labelled input notes (model/augment.py INote) into model batches."""
from __future__ import annotations

import math
from fractions import Fraction as F

import numpy as np
import torch

import model.augment as A
from model.net import (DUR_BINS, INSTRUMENTS, MAX_PARTS, OCT_UNK, ONSET_BINS, PART_DROP, PART_UNK,
                       REAL_UNK)

MAX_NOTES = 384
IGNORE = -100


def ensemble_parts(insts: list[str]) -> tuple[list[int], list[int]]:
    """Instrument ids and slot index (k-th part of that instrument) per part."""
    seen: dict[str, int] = {}
    ids, slots = [], []
    for k in insts:
        ids.append(INSTRUMENTS.index(k))
        slots.append(seen.get(k, 0))
        seen[k] = seen.get(k, 0) + 1
    return ids, slots


def part_class(p: int) -> int:
    return PART_DROP if p == A.DROP else p


def encode(inotes: list[A.INote], insts: list[str], start: F, reveal: np.ndarray | None = None) -> dict:
    """One example. reveal[i] = True: note i's labels are given as committed context
    (always True for context notes). Labels are IGNORE for revealed notes."""
    inotes = inotes[:MAX_NOTES]
    n = len(inotes)
    rv = np.array([x.context for x in inotes], bool)
    if reveal is not None:
        rv |= reveal[:n]
    on = np.array([float(x.onset - start) for x in inotes], np.float32)
    du = np.array([float(x.dur) for x in inotes], np.float32)
    lab_p = np.array([part_class(x.part) for x in inotes], np.int64)
    lab_o = np.array([A.OCTAVES.index(x.octave) for x in inotes], np.int64)
    lab_r = np.array([x.real for x in inotes], np.int64)
    ob = np.array([int(round(float(x.onset % 1) * ONSET_BINS)) % ONSET_BINS for x in inotes], np.int64)
    db = np.array([min(DUR_BINS - 1, max(0, int(round(math.log2(max(float(x.dur), 1 / 48) * 48))))) for x in inotes], np.int64)
    pi, ps = ensemble_parts(insts)
    return {
        "pitch": np.array([x.pitch for x in inotes], np.int64), "onset": on,
        "src": np.array([x.src if 0 <= x.src < 4 else 4 for x in inotes], np.int64), "onset_bin": ob, "dur": du,
        "dur_bin": db, "context": np.array([x.context for x in inotes], np.int64),
        "c_part": np.where(rv, lab_p, PART_UNK), "c_oct": np.where(rv, lab_o, OCT_UNK),
        "c_real": np.where(rv, lab_r, REAL_UNK),
        "y_part": np.where(rv, IGNORE, lab_p), "y_oct": np.where(rv, IGNORE, lab_o),
        "y_real": np.where(rv, IGNORE, lab_r),
        "part_inst": np.array(pi, np.int64), "part_slot": np.array(ps, np.int64), "n_parts": len(insts),
    }


def collate(items: list[dict]) -> dict:
    B = len(items)
    N = max(1, max(len(x["pitch"]) for x in items))
    out = {}
    fill = {"src": 4, "c_part": PART_UNK, "c_oct": OCT_UNK, "c_real": REAL_UNK, "y_part": IGNORE, "y_oct": IGNORE, "y_real": IGNORE}
    for k in ("pitch", "src", "onset", "onset_bin", "dur", "dur_bin", "context", "c_part", "c_oct", "c_real",
              "y_part", "y_oct", "y_real"):
        dt = np.float32 if k in ("onset", "dur") else np.int64
        a = np.full((B, N), fill.get(k, 0), dt)
        if k == "dur":
            a[:] = 1.0
        for i, x in enumerate(items):
            a[i, :len(x[k])] = x[k]
        out[k] = torch.from_numpy(a)
    out["note_mask"] = torch.zeros(B, N, dtype=torch.bool)
    for i, x in enumerate(items):
        out["note_mask"][i, :len(x["pitch"])] = True
    P = MAX_PARTS
    out["part_inst"] = torch.zeros(B, P, dtype=torch.long)
    out["part_slot"] = torch.zeros(B, P, dtype=torch.long)
    out["part_mask"] = torch.zeros(B, P, dtype=torch.bool)
    for i, x in enumerate(items):
        k = x["n_parts"]
        out["part_inst"][i, :k] = torch.from_numpy(x["part_inst"])
        out["part_slot"][i, :k] = torch.from_numpy(x["part_slot"])
        out["part_mask"][i, :k] = True
    return out
