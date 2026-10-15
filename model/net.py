"""Transformer encoder with three per-note heads: part (target parts + DROP),
octave (-24, -12, 0, +12, +24), realisation (5 ops). No pretraining.

Sequence = [one token per target part] + [one token per input note]. Every token
attends to every other token. Part logits = scaled dot product between a note's
state and each part token's state (so any ensemble of <= MAX_PARTS parts works),
plus one learned DROP logit. Committed decisions (partially decoded state, or
revealed labels during training) enter as per-note input features.
"""
from __future__ import annotations

import math

import torch
from torch import nn

MAX_PARTS = 4
INSTRUMENTS = ["violin", "viola", "cello", "flute", "piano"]
N_OCT, N_REAL = 5, 5
PART_DROP, PART_UNK = MAX_PARTS, MAX_PARTS + 1          # committed-part feature values
OCT_UNK, REAL_UNK = N_OCT, N_REAL
ONSET_BINS, DUR_BINS = 24, 16


def fourier(x: torch.Tensor, n: int, scale: float) -> torch.Tensor:
    f = torch.exp(torch.arange(n, device=x.device) * (-math.log(1000.0) / n)) / scale
    a = x[..., None] * f
    return torch.cat([a.sin(), a.cos()], -1)


class Arranger(nn.Module):
    def __init__(self, d=256, layers=6, heads=8, ff=1024, dropout=0.1, src_feature=False):
        super().__init__()
        self.d = d
        # arranger-v2: source part (Vn1 Vn2 Va Vc, 4 = unknown) as an input feature. Off for v1 checkpoints.
        self.src = nn.Embedding(5, d) if src_feature else None
        self.pitch = nn.Embedding(128, d)
        self.onset_bin = nn.Embedding(ONSET_BINS, d)
        self.dur_bin = nn.Embedding(DUR_BINS, d)
        self.time = nn.Linear(64, d)
        self.ctx = nn.Embedding(2, d)
        self.c_part = nn.Embedding(MAX_PARTS + 2, d)
        self.c_oct = nn.Embedding(N_OCT + 1, d)
        self.c_real = nn.Embedding(N_REAL + 1, d)
        self.inst = nn.Embedding(len(INSTRUMENTS), d)
        self.slot = nn.Embedding(MAX_PARTS, d)
        self.kind = nn.Embedding(2, d)   # 0 part token, 1 note token
        layer = nn.TransformerEncoderLayer(d, heads, ff, dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, layers)
        self.norm = nn.LayerNorm(d)
        self.part_q = nn.Linear(d, d)
        self.part_k = nn.Linear(d, d)
        self.drop = nn.Linear(d, 1)
        self.oct = nn.Linear(d, N_OCT)
        self.real = nn.Linear(d, N_REAL)

    def forward(self, b: dict) -> dict:
        """b: pitch, onset (quarters, float), onset_bin, dur (quarters), dur_bin, context, c_part,
        c_oct, c_real: [B, N]; note_mask [B, N] (True = real note); part_inst, part_slot [B, P];
        part_mask [B, P] (True = part present)."""
        t = torch.stack([b["onset"], torch.log2(b["dur"].clamp(min=1 / 48))], -1)
        x = (self.pitch(b["pitch"]) + self.onset_bin(b["onset_bin"]) + self.dur_bin(b["dur_bin"])
             + self.time(torch.cat([fourier(t[..., 0], 16, 1.0), fourier(t[..., 1], 16, 1.0)], -1))
             + self.ctx(b["context"]) + self.c_part(b["c_part"]) + self.c_oct(b["c_oct"])
             + self.c_real(b["c_real"]) + self.kind.weight[1])
        if self.src is not None:
            x = x + self.src(b["src"])
        p = self.inst(b["part_inst"]) + self.slot(b["part_slot"]) + self.kind.weight[0]
        P = p.shape[1]
        h = self.enc(torch.cat([p, x], 1), src_key_padding_mask=~torch.cat([b["part_mask"], b["note_mask"]], 1))
        h = self.norm(h)
        hp, hn = h[:, :P], h[:, P:]
        part = torch.einsum("bnd,bpd->bnp", self.part_q(hn), self.part_k(hp)) / math.sqrt(self.d)
        part = part.masked_fill(~b["part_mask"][:, None, :], -1e9)
        part = torch.cat([part, torch.zeros_like(part[..., :MAX_PARTS - P]).fill_(-1e9), self.drop(hn)], -1)
        return {"part": part, "octave": self.oct(hn), "real": self.real(hn)}   # part: [B, N, MAX_PARTS + 1]
