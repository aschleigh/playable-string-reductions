"""Iterative decoding with constraint propagation (Step 5).

    python -m model.decode --checkpoint model/results/arranger-v1/checkpoint.pt --regime trio [--masked]

Per movement, in windows of 16 quarters with the previous 8 quarters as committed
context (exactly the training layout):
  repeat until every note of the window is decided:
    predict all undecided notes (committed notes enter as context features);
    commit the k = ceil(remaining / 2) most confident (confidence = product of the three
    heads' top probabilities), in confidence order.
  Unmasked: each committed note takes its argmax option per head.
  Masked: each committed note takes its most probable joint option (part x octave x
  realisation, joint probability = product of the heads) whose expanded output notes add
  no hard violation to everything committed so far (GrowingChecker = frozen checker rules).
  DROP never adds a violation, so a feasible option always exists.
Output: arrangement records (decoding/../model/results/<run>/records/<system>__<regime>.jsonl).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model.augment as A  # noqa: E402
from arrangement.decode.growing import GrowingChecker  # noqa: E402
from arrangement.eval.record import ArrangementRecord, load, make_score, save  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402
from model.features import MAX_NOTES, collate, encode  # noqa: E402
from model.net import MAX_PARTS, PART_DROP, Arranger  # noqa: E402

REC = ROOT / "headroom" / "data" / "records"
REFERENCE = {"trio": [[0], [2], [3]], "duo": [[0], [3]]}
TPQ_BASE = 720720   # lcm(1..16); times are exact at TPQ_BASE x (lcm of the source's denominators)


class Committer:
    """Tracks committed labels; in masked mode keeps the checker equal to expand(committed)."""

    def __init__(self, ens, tpq: int, masked: bool, max_dur: F, merge_unisons: bool = True):
        self.masked = masked
        self.ck = GrowingChecker(ens, tpq, int(max_dur * tpq) + 1, capacity=8192) if masked else None
        self.tpq = tpq
        self.slots: dict[int, list[int]] = {}           # input note index -> checker slots
        self.groups: dict[tuple, list[int]] = {}        # arpeggio group -> input note indices
        self.n_fallback = 0                             # failed options (several per note possible)
        self.n_intervened = 0                           # notes whose top joint option was blocked
        self.n_shrunk = 0                               # windows shrunk to fit MAX_NOTES
        # decode v2 (REVIEW R37): a plain note that duplicates a committed plain note of the same part
        # (same onset, same sounding pitch) is merged into it, as the training targets merge unisons
        self.merge_unisons = merge_unisons
        self.plain_at: dict[tuple, int] = {}            # (part, onset, pitch) -> input note index
        self.n_merged = 0

    def _t(self, x: F) -> int:
        t = x * self.tpq
        if t.denominator != 1:
            raise ValueError(f"time {x} not representable at tpq {self.tpq}")
        return int(t)

    def _add(self, notes):
        """Commit output notes; returns (slots, violated)."""
        slots, bad = [], False
        for part, o, d, x in notes:
            try:
                on, en = self._t(o), self._t(o + d)
            except ValueError:                # not on the tick grid (e.g. a 17-note arpeggio): infeasible
                bad = True
                break
            if not 0 <= x <= 127:
                bad = True
                break
            i, added = self.ck.add(on, en, x, part)
            slots.append(i)
            if added:
                bad = True
                break
        return slots, bad

    def _remove(self, slots):
        for i in slots:
            self.ck.uncommit(i)

    def try_commit(self, idx: int, inotes: list[A.INote], part: int, octv: int, real: int) -> bool:
        n = inotes[idx]
        n.part, n.octave, n.real = part, octv, real
        n.merged = False
        ukey = (part, n.onset, n.pitch + octv)
        if self.merge_unisons and part != A.DROP and real == A.PLAIN:
            j = self.plain_at.get(ukey)
            if j is not None and j != idx:
                n.merged = True
                self.slots[idx] = []
                self.n_merged += 1
                return True
        if part == A.DROP or not self.masked:
            if real == A.ARPEGGIATE and part != A.DROP:
                self.groups.setdefault((part, n.onset, n.dur), []).append(idx)
            if self.merge_unisons and part != A.DROP and real == A.PLAIN:
                self.plain_at.setdefault(ukey, idx)
            return True
        if real == A.ARPEGGIATE:
            key = (part, n.onset, n.dur)
            members = self.groups.get(key, []) + [idx]
            old = [s for m in self.groups.get(key, []) for s in self.slots.get(m, [])]
            self._remove(old)
            new_notes = A.expand([inotes[m] for m in members])
            slots, bad = self._add(new_notes)
            if bad:
                self._remove(slots)
                for s in old:
                    self.ck.commit(s, part)
                n.part = A.DROP
                return False
            for m in self.groups.get(key, []):
                self.slots[m] = []
            self.slots[idx] = slots
            self.groups[key] = members
            return True
        slots, bad = self._add(A.expand([n]))
        if bad:
            self._remove(slots)
            n.part = A.DROP
            return False
        self.slots[idx] = slots
        if self.merge_unisons and real == A.PLAIN:
            self.plain_at.setdefault(ukey, idx)
        return True


TIER_RANK = {"top": 0, "bass": 1, "inner": 2}


def decode_movement(net, device, source_notes, insts, ens, masked: bool, tpq: int, melody_first: bool = False):
    """melody_first (decode v3, REVIEW R42): within each pass the notes committed are chosen and ordered by
    voice tier of the source (top, then bass, then inner; arrangement/eval/reduction.voice_tiers), then by
    model confidence, so a held melody note is placed before the inner notes that would block it."""
    src_sorted = sorted(source_notes, key=lambda n: (n[1], n[3], n[2]))
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in src_sorted]
    tier_rank = None
    if melody_first:
        from arrangement.eval.reduction import voice_tiers
        tier_rank = [TIER_RANK[t] for t in voice_tiers(src_sorted)]      # source notes are non-grace (grace dropped)
    decided = np.zeros(len(inotes), bool)
    com = Committer(ens, tpq, masked, max((n.dur for n in inotes), default=F(1)))
    end = max((n.onset for n in inotes), default=F(0))
    w0 = F(0)
    P = len(insts)
    oct_vals = A.OCTAVES
    while w0 <= end:
        # training layout: 16-quarter window + 8 context; halved (both) while it exceeds MAX_NOTES
        wl, cl = A.WINDOW, A.CONTEXT
        while True:
            win = [i for i, n in enumerate(inotes) if w0 - cl <= n.onset < w0 + wl]
            if len(win) <= MAX_NOTES or wl <= F(1, 4):
                break
            wl, cl = wl / 2, cl / 2
        com.n_shrunk += wl < A.WINDOW
        win = win[:MAX_NOTES]
        while True:
            todo = [i for i in win if not decided[i] and inotes[i].onset >= w0]
            if not todo:
                break
            sub = [inotes[i] for i in win]
            for i, n in zip(win, sub):
                n.context = n.onset < w0
            reveal = np.array([decided[i] for i in win], bool)
            ex = encode(sub, insts, w0, reveal)
            b = {k: v.to(device) for k, v in collate([ex]).items()}
            with torch.no_grad():
                out = net(b)
            pp = torch.softmax(out["part"][0], -1).cpu().numpy()
            po = torch.softmax(out["octave"][0], -1).cpu().numpy()
            pr = torch.softmax(out["real"][0], -1).cpu().numpy()
            pos = {i: k for k, i in enumerate(win)}
            conf = sorted(todo, key=lambda i: ((tier_rank[i] if tier_rank is not None else 0),
                                               -(pp[pos[i]].max() * po[pos[i]].max() * pr[pos[i]].max())))
            k = math.ceil(len(todo) / 2)
            for i in conf[:k]:
                j = pos[i]
                part_ids = list(range(P)) + [PART_DROP]
                if not masked:
                    pc = part_ids[int(np.argmax(pp[j][part_ids]))]
                    com.try_commit(i, inotes, A.DROP if pc == PART_DROP else pc,
                                   oct_vals[int(po[j].argmax())], int(pr[j].argmax()))
                else:
                    opts = sorted(((pp[j][pc] * po[j][o] * pr[j][r], pc, o, r)
                                   for pc in part_ids for o in range(len(oct_vals)) for r in range(5)), reverse=True)
                    for rank, (_, pc, o, r) in enumerate(opts):
                        if pc == PART_DROP:
                            com.try_commit(i, inotes, A.DROP, 0, A.PLAIN)
                            break
                        if com.try_commit(i, inotes, pc, oct_vals[o], r):
                            break
                        com.n_fallback += 1
                        com.n_intervened += rank == 0
                decided[i] = True
        w0 += wl
    return inotes, com


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--regime", default="trio")
    ap.add_argument("--masked", action="store_true")
    ap.add_argument("--melody-first", action="store_true", help="decode v3 (R42): commit by voice tier first")
    ap.add_argument("--out-dir", default=None, help="records directory (default: <checkpoint dir>/records)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    a = ap.parse_args(argv)
    ck = torch.load(a.checkpoint, map_location="cpu")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = Arranger(**ck["cfg"]["net"]).to(device).eval()
    net.load_state_dict(ck["model"])
    ens = load_ensemble(a.regime)
    insts = [i.key for i in ens.instruments]
    parts = [(n, i.key) for n, i in zip(ens.part_names, ens.instruments)]
    base = load(REC / f"continuity__{a.regime}.jsonl")[a.shard::a.nshards][: a.limit]
    system = "arranger_masked" if a.masked else "arranger"
    recs, diag = [], []
    for r in base:
        # every expanded time is a source time split into k <= 16 parts: source lcm x lcm(1..16)
        tpq = TPQ_BASE * math.lcm(1, *{x.denominator for n in r.source.notes for x in (n[1], n[2])})
        inotes, com = decode_movement(net, device, r.source.notes, insts, ens, a.masked, tpq, a.melody_first)
        out = A.expand(inotes)
        recs.append(ArrangementRecord(
            system=system, system_version=f"{ck['cfg']['run_name']}@{ck['step']}", seed=None,
            input_id=r.input_id, ensemble=a.regime, source=r.source, output=make_score(parts, out), bars=r.bars,
            reference_source_parts=tuple(tuple(x) for x in REFERENCE[a.regime]), meta=r.meta))
        real = np.bincount([n.real for n in inotes if n.part != A.DROP], minlength=5)
        diag.append({"input_id": r.input_id, "n_in": len(inotes), "n_out": len(out),
                     "n_drop": sum(n.part == A.DROP for n in inotes), "realisation_counts": real.tolist(),
                     "octave_nonzero": sum(n.octave != 0 for n in inotes if n.part != A.DROP),
                     "masked_fallbacks": com.n_fallback, "masked_interventions": com.n_intervened,
                     "unisons_merged": com.n_merged, "decode_version": 3 if a.melody_first else 2,
                     "windows_shrunk": com.n_shrunk})
        print(r.input_id[:50], diag[-1], flush=True)
    od = Path(a.out_dir) if a.out_dir else Path(a.checkpoint).parent / "records"
    od.mkdir(parents=True, exist_ok=True)
    tag = f"{system}__{a.regime}" + (f".{a.shard}" if a.nshards > 1 else "")
    save(recs, od / f"{tag}.jsonl")
    (od / f"{tag}.diag.json").write_text(json.dumps(diag, indent=1))


if __name__ == "__main__":
    main()
