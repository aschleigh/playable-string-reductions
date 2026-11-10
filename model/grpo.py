"""GRPO on the masked arranger (BLOCK4.md 2a-2d). The mask stays on; the reward is the cost of masking.

    python -m model.grpo contexts --run arranger-v2b --shard S --nshards N   (GPU; once per base run)
    python -m model.grpo train --setting C --run-name rl-C [--steps N] [--workers 48]
    python -m model.grpo smoke                                               (tests + timing, few windows)

Sample unit: a 16-quarter window of a train movement. Its context (the 8 previous quarters, and any
earlier note sounding into them) is fixed per window: arranger-v2b's greedy masked decode, precomputed
("contexts"). All G samples of a group start from that same committed state.

Trajectory: the multi-pass commit decisions of the window (model/decode.py loop: each pass commits the
ceil(remaining / 2) most confident undecided notes, in confidence order). Each committed note samples a
joint option a = (part, octave, realisation), or DROP, from

    pi(a | s, M) = p(a | s) M(a) / sum_b p(b | s) M(b)

p = product of the three heads (DROP = p_part[DROP]); M = candidate set and feasible. The candidate
set is the old policy's top joint options covering >= CAND_MASS of the probability (at most CAND_MAX),
plus DROP. Feasibility: the frozen checker (GrowingChecker via model/decode.Committer), given everything
committed so far, including earlier notes of the same pass.

Recorded per decision and replayed in the update: the pass's network input, the candidate ids, the
feasibility bits, the chosen candidate, and log pi_old. The update never calls the checker; it
renormalises the new policy over the STORED mask. Tests: tests/test_grpo.py (ratio identity, replay
determinism, sampling distribution, masked gradient, the mask-unaware bug fails).

Reward (BLOCK4.md 2b), per window: R = F_w + w_H H - lambda_DS DS + G.
Loss: PPO-clipped GRPO, group-normalised advantages, per-decision token mean, KL(k3) to the frozen
base policy under the same stored masks. Train split only; validation on the dev split.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import pickle
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction as F
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model.augment as A  # noqa: E402
from arrangement.eval.fidelity import chroma_per_beat  # noqa: E402
from arrangement.eval.reduction import _sounding, _sounding_sets, voice_tiers  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402

RL = ROOT / "model" / "results" / "rl"
TPQ_BASE = 720720
REGIMES = ("trio", "duo")
FK_REGIMES = ("solo_flute", "piano")          # BLOCK6 Amendment A (R73)
DROP_SLOT, N_OCT, N_REAL = 4, 5, 5
DROP_ID = DROP_SLOT * N_OCT * N_REAL          # the single DROP joint option
N_JOINT = DROP_ID                             # non-DROP joint options


def configure(n_real: int) -> None:
    """Set the joint-option layout for a checkpoint's realisation count (5, or 6 with CUT, R70). Call before
    any rollout or update with that network; forked workers inherit it."""
    global N_REAL, DROP_ID, N_JOINT
    N_REAL = n_real
    DROP_ID = N_JOINT = DROP_SLOT * N_OCT * n_real
CAND_MASS, CAND_MAX = 0.999, 16
G_MIN_NOTES = 8                               # retention floor applies to a tier with >= 8 window notes (R31)
TIERS = ("top", "inner", "bass")
# retention floors for G: 0.9 x the oracle-under-mask ("model" fallback) retention, BLOCK4.md 2b
RHO = {"trio": {"top": 0.88, "inner": 0.83, "bass": 0.89}, "duo": {"top": 0.85, "inner": 0.62, "bass": 0.84}}
SETTINGS = {
    "A": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 1.0, "kappa": 5.0},
    "B": {"w": {"top": 1.0, "bass": 1.0, "inner": 0.7}, "wH": 0.25, "lam": 0.25, "kappa": 5.0},
    "C": {"w": {"top": 1.0, "bass": 1.0, "inner": 1.0}, "wH": 0.25, "lam": 0.0, "kappa": 5.0},
    # R36: A, plus "kept" requires the note held >= 75% of its written duration (no credit for re-striking
    # a held note as repeats, the rl-C / rl-AZ2 hack)
    "A2": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 1.0, "kappa": 5.0, "dur_match": 0.75},
    # R38: A2 with a 3x double-stop penalty (rl-SA2Z missed only the double-stop criterion), and the same with a
    # 90% duration rule (residual repeat-splitting in the duo)
    "A3": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 3.0, "kappa": 5.0, "dur_match": 0.75},
    "A3D9": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 3.0, "kappa": 5.0, "dur_match": 0.9},
    # R40 (user-approved reward change): duration-weighted fidelity, 0.8 credit for a note an octave away / in
    # another part, so the melody can drop an octave or move to the cello instead of being dropped; lambda 2 / 3
    "M2": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 2.0, "kappa": 5.0, "dur_match": 0.75,
           "dur_weight": True, "reloc": 0.8},
    "M3": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 3.0, "kappa": 5.0, "dur_match": 0.75,
           "dur_weight": True, "reloc": 0.8},
    # BLOCK5 Step 4 (R51): M2 plus the penalty-only idiomatic part term of P (model/idiom.py), weight 0.5 / 1.0;
    # retention floors on top and bass only (R53: the S2 targets drop inner voices by the user's choice)
    "MI05": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 2.0, "kappa": 5.0, "dur_match": 0.75,
             "dur_weight": True, "reloc": 0.8, "idiom": 0.5, "floors": ("top", "bass")},
    "MI10": {"w": {"top": 1.0, "bass": 0.8, "inner": 0.25}, "wH": 0.25, "lam": 2.0, "kappa": 5.0, "dur_match": 0.75,
             "dur_weight": True, "reloc": 0.8, "idiom": 1.0, "floors": ("top", "bass")},
    # BLOCK6 Amendment A2 (R73), from control-FK2. Floors are 0.9 x the F3 / K target's retention in the same window
    # (target_floor); a CUT note counts as held (cut_held: held >= dur_match x its CUT length). Flute: melody only,
    # breath shortfall max(0, longest unbroken run - 12 quarters) / 16, and a guard on CUT share above 1.5 x the
    # target's. Piano: the conditional feasibility term (--feas) carries the main signal.
    "F05": {"w": {"top": 1.0, "bass": 0.0, "inner": 0.0}, "wH": 0.25, "lam": 0.0, "kappa": 5.0, "dur_match": 0.75,
            "dur_weight": True, "reloc": 0.8, "cut_held": True, "target_floor": 0.9, "floors": ("top",),
            "breath": 0.5, "breath_q": 12, "cut_guard": 2.0, "cut_ratio": 1.5},
    "F10": {"w": {"top": 1.0, "bass": 0.0, "inner": 0.0}, "wH": 0.25, "lam": 0.0, "kappa": 5.0, "dur_match": 0.75,
            "dur_weight": True, "reloc": 0.8, "cut_held": True, "target_floor": 0.9, "floors": ("top",),
            "breath": 1.0, "breath_q": 12, "cut_guard": 2.0, "cut_ratio": 1.5},
    "K": {"w": {"top": 1.0, "bass": 1.0, "inner": 0.5}, "wH": 0.25, "lam": 0.0, "kappa": 5.0, "dur_match": 0.75,
          "dur_weight": True, "reloc": 0.8, "cut_held": True, "target_floor": 0.9, "floors": ("top", "bass")},
}
TARGETS = {"solo_flute": ("fk2", "flute"), "piano": ("fk2", "piano")}   # target file tag, key in it (A2 floors)

# BLOCK7 + Amendment A merged (R79): reward R8, the same principles for every instrument. On top of each regime's base
# reward (strings: the user's priorities; flute / piano: Amendment A2): a cost per extra output note (no credit for
# splitting), melody line integrity (no octave jumps the source line does not have), melody-first rollouts; strings also
# judge double stops against the composers' own rate (criterion B').
RHO7 = {"trio": {"top": 0.889, "bass": 0.885}, "duo": {"top": 0.852, "bass": 0.805}}   # 0.9 x control-S2c dev retention
FEED = {"trio": {0: (0, 1), 1: (2,), 2: (3,)}, "duo": {0: (0, 1), 1: (2, 3)}}
_R8 = {"note_cost": 0.05, "line_break": 0.5, "melody_first": True,
       "reloc_shifts": (-12, 12)}   # R8.1 (R80/R81): no credit two octaves away (the inner line term was dropped, R81)
for _lam in (2, 4):
    SETTINGS[f"R8S{_lam}"] = {"w": {"top": 1.0, "bass": 0.8, "inner": 0.1}, "wH": 0.25, "lam": float(_lam), "kappa": 5.0,
                              "dur_match": 0.75, "dur_weight": True, "reloc": 0.8, "floors": ("top", "bass"), "rho": RHO7,
                              "ds_mode": "excess", **_R8}
SETTINGS["R8F05"] = {**SETTINGS["F05"], **_R8}
SETTINGS["R8F10"] = {**SETTINGS["F10"], **_R8}
SETTINGS["R8K"] = {**SETTINGS["K"], **_R8}
_MF = {"on": False}     # melody-first rollouts in this process (set from the setting by the workers)


def _ds_moments(ns, w0, w1):
    """Double-stop moments (2+ notes sounding at an onset) with the onset in [w0, w1); ns = [(on, end, pitch)]."""
    ns = sorted(ns)
    cnt, active, k = 0, [], 0
    for t in sorted({q[0] for q in ns}):
        while k < len(ns) and ns[k][0] <= t:
            active.append(ns[k]); k += 1
        active = [q for q in active if q[1] > t]
        cnt += len(active) >= 2 and w0 <= t < w1
    return cnt


def ds_excess(m, regime, w0, w1, allout):
    """R8 strings / criterion B' inside a window: per output part, its double-stop moments above the composers' rate in
    the source parts that feed it (each source part's own double stops), floored at 0; summed."""
    lo = w0 - A.CONTEXT
    out = 0.0
    for p, feed in FEED[regime].items():
        on = [(o, o + d, x) for q, o, d, x in allout if q == p and d > 0]
        n_out = sum(1 for o, _, _ in on if w0 <= o < w1)
        if not n_out:
            continue
        src_ds = src_n = 0
        for sp in feed:
            sn = [(o, o + d, x) for q, o, d, x in m.src if q == sp and d > 0 and o + d > lo and o < w1]
            src_ds += _ds_moments(sn, w0, w1)
            src_n += sum(1 for o, _, _ in sn if w0 <= o < w1)
        rate = src_ds / src_n if src_n else 0.0
        out += max(0.0, _ds_moments(on, w0, w1) - rate * n_out)
    return out


def line_breaks(m, src_ids, out_notes, dm: float, tier: str = "top") -> tuple[int, int]:
    """R8 melody line integrity: over consecutive kept top-tier source notes (in time order), how often the octave shift
    between source and output changes (the line jumps a register the source line does not). A whole phrase moved an
    octave keeps one shift and costs nothing. Returns (breaks, kept top notes)."""
    by = defaultdict(list)
    for _, o, d, x in out_notes:
        if d > 0:
            by[x].append((o, d))
    # top: one line in time order; inner (R8.1): one line per source part
    lines = defaultdict(list)
    for i in sorted((i for i in src_ids if m.tiers[i] == tier), key=lambda i: m.src[i][1]):
        lines[0 if tier == "top" else m.src[i][0]].append(i)
    breaks = kept = 0
    for ids in lines.values():
        b_, k_ = _line_shifts(m, ids, by, dm)
        breaks += b_; kept += k_
    return breaks, kept


def _line_shifts(m, ids, by, dm):
    shifts = []
    for i in ids:
        _, o, d, x = m.src[i]
        if m.cut and m.cut[i][0] is not None and m.cut[i][0] < o + d:
            d = min(d, m.cut[i][0] - o)          # a CUT note counts as held to its cut point (as cut_held)
        for s_ in (0, -12, 12, -24, 24):
            if any(abs(o - y) < F(1, 4) and yd >= dm * d for y, yd in by.get(x + s_, ())):
                shifts.append(s_)
                break
    return sum(a != b for a, b in zip(shifts, shifts[1:])), len(shifts)


def joint_id(pc: int, o: int, r: int) -> int:
    return DROP_ID if pc == DROP_SLOT else (pc * N_OCT + o) * N_REAL + r


def decode_id(a: int) -> tuple[int, int, int]:
    if a == DROP_ID:
        return DROP_SLOT, A.OCTAVES.index(0), A.PLAIN
    pc, rest = divmod(a, N_OCT * N_REAL)
    o, r = divmod(rest, N_REAL)
    return pc, o, r


# ------------------------------------------------------------ data

@dataclass
class Movement:
    key: str
    src: list                      # (part, onset, dur, pitch), decode order
    tiers: list
    tpq: int
    sidx: dict                     # source sounding-set index (reduction._sounding_sets)
    ctx: dict = field(default_factory=dict)   # regime -> greedy masked labels [(part, octave, real)]
    cut: list = field(default_factory=list)   # R70: (cut_end, cut_kind) per source note, from the whole movement


def load_split(split: str) -> list[Movement]:
    out = []
    for line in open(ROOT / "model" / "data" / f"{split}.jsonl"):
        d = json.loads(line)
        notes = [(int(p), F(o), F(du), int(x)) for p, o, du, x in d["notes"]]
        src = sorted(notes, key=lambda n: (n[1], n[3], n[2]))
        tpq = TPQ_BASE * math.lcm(1, *{x.denominator for n in src for x in (n[1], n[2])})
        tiers = voice_tiers(src)
        tmp = [A.INote(o, du, x, src=p) for p, o, du, x in src]
        A.assign_cut_ends(tmp, tiers)
        out.append(Movement(d["key"], src, tiers, tpq, _sounding_sets(src), cut=[(n.cut_end, n.cut_kind) for n in tmp]))
    return out


def attach_contexts(mvs: list[Movement], run: str, split: str = "train"):
    by = {m.key: m for m in mvs}
    for p in sorted((RL / "contexts").glob(f"{run}__{split}.*.pkl")):
        for key, d in pickle.load(open(p, "rb")).items():
            if key in by:
                by[key].ctx.update(d["greedy"])
    return mvs


def windows(m: Movement, max_notes: int):
    """Window starts (multiples of 16 quarters, as in decoding) with 4..max_notes notes in the window+context."""
    if not m.src:
        return []
    end = max(n[1] for n in m.src)
    ons = [n[1] for n in m.src]
    res, w0 = [], F(0)
    while w0 <= end:
        a, b, c = bisect.bisect_left(ons, w0 - A.CONTEXT), bisect.bisect_left(ons, w0), bisect.bisect_left(ons, w0 + A.WINDOW)
        if c - b >= 4 and c - a <= max_notes:
            res.append(w0)
        w0 += A.WINDOW
    return res


# ------------------------------------------------------------ committer with probing

def _committer_cls():
    from model.decode import Committer

    class RLCommitter(Committer):
        def probe(self, idx, inotes, part, octv, real) -> bool:
            """Would committing this option add a violation? State is restored exactly."""
            n = inotes[idx]
            saved = (n.part, n.octave, n.real, n.merged)
            ukey = (part, n.onset, n.pitch + octv)
            had_key, n_merged = ukey in self.plain_at, self.n_merged
            if part == A.DROP:
                return True
            if real == A.ARPEGGIATE:
                key = (part, n.onset, n.dur)
                old_members = list(self.groups.get(key, []))
                old_slots = {m: list(self.slots.get(m, [])) for m in old_members}
                ok = self.try_commit(idx, inotes, part, octv, real)
                if ok:
                    self._remove(self.slots.pop(idx))
                    for m, sl in old_slots.items():
                        self.slots[m] = sl
                        for s in sl:
                            self.ck.commit(s, part)
                    if old_members:
                        self.groups[key] = old_members
                    else:
                        del self.groups[key]
            else:
                ok = self.try_commit(idx, inotes, part, octv, real)
                if ok:
                    self._remove(self.slots.pop(idx))
            n.part, n.octave, n.real, n.merged = saved
            if not had_key:
                self.plain_at.pop(ukey, None)
            self.n_merged = n_merged
            if not ok:
                self.slots.pop(idx, None)
            return ok
    return RLCommitter


# ------------------------------------------------------------ policy helpers

def joint_logp_np(lp_part, lp_oct, lp_real, P: int) -> np.ndarray:
    """[N, N_JOINT + 1] joint log-probs: ids 0..N_JOINT-1 = (part<4, octave, realisation), N_JOINT = DROP
    (101 for n_real 5, 121 for n_real 6). Parts >= P: -inf."""
    N = lp_part.shape[0]
    assert lp_real.shape[1] == N_REAL, "configure(n_real) not called for this network"
    J = lp_part[:, :4, None, None] + lp_oct[:, None, :, None] + lp_real[:, None, None, :]
    J = J.reshape(N, N_JOINT).copy()
    per = N_OCT * N_REAL
    for pc in range(P, 4):
        J[:, pc * per:(pc + 1) * per] = -np.inf
    return np.concatenate([J, lp_part[:, DROP_SLOT:DROP_SLOT + 1]], 1)


def candidates(jl: np.ndarray) -> np.ndarray:
    """Top joint options covering CAND_MASS (at most CAND_MAX), excluding DROP, then DROP appended."""
    p = np.exp(jl[:N_JOINT])
    order = np.argsort(-p, kind="stable")
    cum, out = 0.0, []
    for a in order[:CAND_MAX]:
        if not np.isfinite(jl[a]):
            break
        out.append(int(a))
        cum += p[a]
        if cum + math.exp(jl[N_JOINT]) >= CAND_MASS:
            break
    return np.array(out + [DROP_ID], np.int64)


def masked_logp_np(jl_c: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """log pi over the candidates under the mask (-inf where masked)."""
    x = np.where(mask, jl_c, -np.inf)
    m = x.max()
    return x - (m + math.log(np.exp(x - m).sum()))


def sample_masked(jl_c, mask, rng) -> int:
    lp = masked_logp_np(jl_c, mask)
    p = np.exp(lp)
    return int(rng.choice(len(p), p=p / p.sum()))


# ------------------------------------------------------------ rollout

@dataclass
class Trajectory:
    passes: list           # encoded network inputs (numpy dicts), one per pass
    dec_pass: np.ndarray   # [D] pass index
    dec_pos: np.ndarray    # [D] position of the note in the pass input
    cands: list            # D arrays of candidate ids
    masks: list            # D bool arrays
    chosen: np.ndarray     # [D] index into cands
    logp_old: np.ndarray   # [D] masked log-prob at rollout
    intervened: np.ndarray  # [D] the policy's top joint option (incl. DROP) was infeasible
    labels: list           # final (part, octave, real) of the window notes
    out_notes: list        # expanded output notes of the window notes
    reward: float = 0.0
    parts: dict = field(default_factory=dict)


def _setup_window(m: Movement, regime: str, w0: F, ens):
    """Input notes [context ∪ window], with the context committed from the greedy labels."""
    ctx = m.ctx[regime]
    lo = w0 - A.CONTEXT
    idx = [i for i, n in enumerate(m.src) if (lo <= n[1] < w0 + A.WINDOW) or (n[1] < lo and n[1] + n[2] > lo)]
    inotes = [A.INote(m.src[i][1], m.src[i][2], m.src[i][3], src=m.src[i][0], cut_end=m.cut[i][0], cut_kind=m.cut[i][1])
              for i in idx]
    com = _committer_cls()(ens, m.tpq, True, max((n.dur for n in inotes), default=F(1)))
    win, todo = [], []
    for k, i in enumerate(idx):
        n = inotes[k]
        if n.onset < w0:
            p, oc, re = ctx[i]
            if not com.try_commit(k, inotes, p, oc, re):     # the greedy decode was feasible; a subset is too
                n.part = A.DROP
            n.context = True
            if n.onset >= lo:
                win.append(k)
        else:
            win.append(k)
            todo.append(k)
    return idx, inotes, com, win, todo


TIER_RANK8 = {"top": 0, "bass": 1, "inner": 2}     # = model.decode.TIER_RANK (decode v3, melody-first; R8)


class RolloutState:
    """One window sample, advanced pass by pass. The network is outside: next_input() gives the pass's
    encoded input, apply() takes the network's log-probs for it and commits that pass's notes (checker,
    candidates, masked sampling), finish() returns the Trajectory. rollout() drives it with a local
    network; the lockstep engine drives many at once with one batched GPU forward per pass."""

    def __init__(self, m: Movement, regime: str, w0: F, rng, greedy: bool = False, timing: Counter | None = None):
        self.m, self.regime, self.w0, self.rng, self.greedy = m, regime, w0, rng, greedy
        self.timing = timing if timing is not None else Counter()
        ens = load_ensemble(regime)
        self.insts = [i.key for i in ens.instruments]
        self.P = len(self.insts)
        t0 = time.perf_counter()
        self.idx, self.inotes, self.com, self.win, self.todo_all = _setup_window(m, regime, w0, ens)
        self.timing["setup_s"] += time.perf_counter() - t0
        self.decided = np.zeros(len(self.inotes), bool)
        for k in self.win:
            self.decided[k] = self.inotes[k].onset < w0
        self.passes, self.dp, self.dpos, self.cands, self.masks = [], [], [], [], []
        self.chosen, self.lpo, self.interv = [], [], []
        self.pos = {k: j for j, k in enumerate(self.win)}
        self._todo = None

    def next_input(self):
        from model.features import encode
        todo = [k for k in self.todo_all if not self.decided[k]]
        if not todo:
            return None
        self._todo = todo
        ex = encode([self.inotes[k] for k in self.win], self.insts, self.w0,
                    np.array([self.decided[k] for k in self.win], bool))
        self.passes.append(ex)
        return ex

    def apply(self, lp_part, lp_oct, lp_real):
        """log-probs [n_win, 5] (float64) for the input last returned by next_input()."""
        t0 = time.perf_counter()
        J = joint_logp_np(lp_part, lp_oct, lp_real, self.P)
        pp, po, pr = np.exp(lp_part), np.exp(lp_oct), np.exp(lp_real)
        pos, todo, com, inotes = self.pos, self._todo, self.com, self.inotes
        conf = sorted(todo, key=lambda k: ((TIER_RANK8[self.m.tiers[self.idx[k]]] if _MF["on"] else 0),
                                           -(pp[pos[k]].max() * po[pos[k]].max() * pr[pos[k]].max())))
        pi = len(self.passes) - 1
        for k in conf[:math.ceil(len(todo) / 2)]:
            j = pos[k]
            c = candidates(J[j])
            t2 = time.perf_counter()
            mk = np.array([com.probe(k, inotes, *_labels(a)) for a in c], bool)
            self.timing["checker_s"] += time.perf_counter() - t2
            self.timing["probes"] += len(c)
            top = int(np.argmax(J[j]))
            self.interv.append(top != DROP_ID and not (top in c and mk[list(c).index(top)]))
            ch = int(np.argmax(np.where(mk, J[j][c], -np.inf))) if self.greedy else sample_masked(J[j][c], mk, self.rng)
            ok = com.try_commit(k, inotes, *_labels(int(c[ch])))
            assert ok, "a feasible candidate failed to commit"
            self.dp.append(pi); self.dpos.append(j); self.cands.append(c); self.masks.append(mk); self.chosen.append(ch)
            self.lpo.append(masked_logp_np(J[j][c], mk)[ch])
            self.decided[k] = True
        self.timing["apply_s"] += time.perf_counter() - t0

    def finish(self) -> "Trajectory":
        inotes, todo_all = self.inotes, self.todo_all
        out_notes = A.expand([inotes[k] for k in todo_all])
        tr = Trajectory(self.passes, np.array(self.dp, np.int64), np.array(self.dpos, np.int64), self.cands, self.masks,
                        np.array(self.chosen, np.int64), np.array(self.lpo, np.float64), np.array(self.interv, bool),
                        [(inotes[k].part, inotes[k].octave, inotes[k].real) for k in todo_all], out_notes)
        tr.parts["_ctx_notes"] = A.expand([n for n in inotes if n.onset < self.w0])
        tr.parts["_src_idx"] = [self.idx[k] for k in todo_all]
        self.timing["notes"] += len(todo_all)
        return tr


def _log_softmax_rows(out, i: int, n: int):
    import torch
    return tuple(torch.log_softmax(out[h][i, :n].double(), -1).cpu().numpy() for h in ("part", "octave", "real"))


def rollout(net, m: Movement, regime: str, w0: F, rng, greedy: bool = False, timing: Counter | None = None):
    """One window sample with a local network (tests, and the per-worker CPU path)."""
    import torch
    from model.features import collate
    st = RolloutState(m, regime, w0, rng, greedy, timing)
    t0 = time.perf_counter()
    while (ex := st.next_input()) is not None:
        t1 = time.perf_counter()
        with torch.no_grad():
            out = net(collate([ex]))
        st.timing["net_s"] += time.perf_counter() - t1
        st.apply(*_log_softmax_rows(out, 0, len(ex["pitch"])))
    st.timing["rollout_s"] += time.perf_counter() - t0
    return st.finish()


def _labels(a: int):
    pc, o, r = decode_id(a)
    return (A.DROP if pc == DROP_SLOT else pc), A.OCTAVES[o], r


# ------------------------------------------------------------ reward

def kept_weights(m: Movement, src_ids, out_notes, setting: dict):
    """Per tier: (kept weight, total weight, note count) of source notes in the output.
    Kept: an output note (any part) with the same pitch, onset within a 16th and duration >= dur_match x the
    written duration. R40 (settings M*): weights are durations in quarters when dur_weight, and a note found
    only an octave or two away (same onset/duration rule, any part) earns `reloc` credit."""
    by = defaultdict(list)
    for _, o, d, x in out_notes:
        if d > 0:
            by[x].append((o, d))
    dm, rel, dw = setting.get("dur_match", 0.0), setting.get("reloc", 0.0), setting.get("dur_weight", False)
    ch = setting.get("cut_held", False)

    def hit(x, o, d):
        return any(abs(o - y) < F(1, 4) and yd >= dm * d for y, yd in by.get(x, ()))
    kept, n, cnt = Counter(), Counter(), Counter()
    for i in src_ids:
        _, o, d, x = m.src[i]
        t = m.tiers[i]
        wt = float(d) if dw else 1.0
        n[t] += wt
        cnt[t] += 1
        # A2 (cut_held): a CUT note counts as held, so the length to match is the shorter CUT length
        dh = min(d, m.cut[i][0] - o) if ch and m.cut and m.cut[i][0] is not None else d
        if hit(x, o, dh):
            kept[t] += wt
        elif rel and any(hit(x + s, o, dh) for s in setting.get("reloc_shifts", (-12, 12, -24, 24))):
            kept[t] += rel * wt
    return kept, n, cnt


def longest_run(notes, lo, hi) -> float:
    """Longest unbroken run (quarters) among runs that overlap [lo, hi); a rest of an eighth or more breaks a run
    (as model/dev_fk.py)."""
    ns = sorted((o, o + d) for _, o, d, _ in notes if d > 0)
    best, start, prev = 0.0, None, None
    for a, b in ns + [(None, None)]:
        if a is None or prev is None or a - prev >= F(1, 2):
            if prev is not None and prev > lo and start < hi:
                best = max(best, float(prev - start))
            if a is None:
                break
            start = a
        prev = b if prev is None else max(prev, b)
    return best


_TARGET_LABELS: dict = {}
_TARGET_WIN: dict = {}


def target_window(m: Movement, regime: str, w0: F, setting: dict) -> dict:
    """A2: the F3 / K target's retention per tier and CUT share in this window (floors and the CUT guard)."""
    ck = (m.key, regime, w0, id(setting))
    if ck in _TARGET_WIN:
        return _TARGET_WIN[ck]
    tag, key = TARGETS[regime]
    if tag not in _TARGET_LABELS:
        _TARGET_LABELS[tag] = pickle.load(open(RL / f"targets_{tag}__train.pkl", "rb"))
    if key in _TARGET_LABELS[tag].get(m.key, {}):
        labs = _TARGET_LABELS[tag][m.key][key]
    else:                                    # a dev movement (R8 reward gate): build the F3 / K target on the fly
        from collections import Counter as _C
        from model.targets_fk import build_flute_cut, build_piano
        labs = (build_flute_cut if key == "flute" else build_piano)(m, _C())
        _TARGET_LABELS[tag].setdefault(m.key, {})[key] = labs
    w1 = w0 + A.WINDOW
    inotes = [A.INote(o, d, x, part=p, octave=oc, real=re, src=sp, cut_end=m.cut[i][0], cut_kind=m.cut[i][1])
              for i, ((sp, o, d, x), (p, oc, re)) in enumerate(zip(m.src, labs))]
    near = [n for n in inotes if w0 - A.WINDOW <= n.onset < w1 + A.WINDOW]
    src_ids = [i for i, q in enumerate(m.src) if w0 <= q[1] < w1 and q[2] > 0]
    kept, n, _ = kept_weights(m, src_ids, A.expand(near), setting)
    played = [labs[i][2] for i in src_ids if labs[i][0] != A.DROP]
    _TARGET_WIN[ck] = {"ret": {t: kept[t] / n[t] for t in TIERS if n[t]},
                       "cut_share": (sum(r == A.CUT for r in played) / len(played)) if played else 0.0}
    return _TARGET_WIN[ck]


def window_reward(m: Movement, regime: str, w0: F, tr: Trajectory, setting: dict) -> dict:
    w1 = w0 + A.WINDOW
    src_ids = [i for i, n in enumerate(m.src) if w0 <= n[1] < w1 and n[2] > 0]
    kept, n, cnt = kept_weights(m, src_ids, tr.out_notes, setting)
    w = setting["w"]
    den = sum(w[t] * n[t] for t in TIERS)
    Fw = sum(w[t] * kept[t] for t in TIERS) / den if den else 0.0
    allout = list(tr.out_notes) + list(tr.parts["_ctx_notes"])
    Cs = chroma_per_beat(tuple(m.src), w0, w1)
    Co = chroma_per_beat(tuple(allout), w0, w1)
    nb, na = np.linalg.norm(Cs, axis=1), np.linalg.norm(Co, axis=1)
    sel = nb > 0
    H = float(np.where(na[sel] > 0, (Co[sel] * Cs[sel]).sum(1) / np.maximum(na[sel] * nb[sel], 1e-300), 0).mean()) if sel.any() else 0.0
    per_part = defaultdict(list)
    for p, o, d, x in allout:
        if d > 0:
            per_part[p].append((o, o + d, x))
    un = 0
    for ns in per_part.values():
        ns.sort()
        active, k = [], 0
        for t in sorted({q[0] for q in ns}):
            while k < len(ns) and ns[k][0] <= t:
                active.append(ns[k]); k += 1
            active = [q for q in active if q[1] > t]
            if len(active) >= 2 and w0 <= t < w1:
                ps = {q[2] for q in active}
                un += not any(ps <= _sounding(ix, t) for ix in m.sidx.values())
    DS = un / max(1, len(src_ids))
    if setting.get("ds_mode") == "excess":   # R8 strings: only double stops above the composers' own rate (B')
        DS = ds_excess(m, regime, w0, w1, allout) / max(1, len(src_ids))
    ret = {t: kept[t] / n[t] for t in TIERS if n[t]}
    # floors only where the window has enough notes in the tier for a rate to mean anything (R31)
    fl = setting.get("floors", TIERS)
    extra = {}
    if setting.get("target_floor"):          # A2: 0.9 x the target's retention in this window
        tw = target_window(m, regime, w0, setting)
        rho = {t: setting["target_floor"] * tw["ret"].get(t, 0.0) for t in TIERS}
    else:
        rho = setting.get("rho", RHO)[regime]
    G = -setting["kappa"] * sum(max(0.0, rho[t] - ret[t]) for t in ret if cnt[t] >= G_MIN_NOTES and t in fl)
    R = Fw + setting["wH"] * H - setting["lam"] * DS + G
    if setting.get("breath"):                # A2 flute: breath shortfall
        L = longest_run(allout, w0, w1)
        extra["run_q"] = L
        extra["B"] = max(0.0, L - setting["breath_q"]) / float(A.WINDOW)
        R -= setting["breath"] * extra["B"]
    if setting.get("cut_guard"):             # A2 flute: CUT share above cut_ratio x the target's
        played = [lab[2] for lab in tr.labels if lab[0] != A.DROP]
        cs = (sum(r == A.CUT for r in played) / len(played)) if played else 0.0
        extra["cut_share"], extra["cut_share_target"] = cs, tw["cut_share"]
        extra["C"] = max(0.0, cs - setting["cut_ratio"] * tw["cut_share"])
        R -= setting["cut_guard"] * extra["C"]
    if setting.get("note_cost"):             # R8: output notes beyond the kept source notes (repeats, tremolo, splits)
        kept_in = sum(1 for lab in tr.labels if lab[0] != A.DROP)
        extra["Nx"] = max(0, len(tr.out_notes) - kept_in) / max(1, len(src_ids))
        R -= setting["note_cost"] * extra["Nx"]
    if setting.get("line_break"):            # R8: melody line integrity
        b_, k_ = line_breaks(m, src_ids, tr.out_notes, setting.get("dur_match", 0.0))
        extra["LB"] = b_ / max(1, k_)
        R -= setting["line_break"] * extra["LB"]
    if setting.get("inner_line_break"):      # R8.1: inner voices keep their register line as well
        b_, k_ = line_breaks(m, src_ids, tr.out_notes, setting.get("dur_match", 0.0), "inner")
        extra["LBi"] = b_ / max(1, k_)
        R -= setting["inner_line_break"] * extra["LBi"]
    Iterm, Iz = 0.0, float("nan")
    if setting.get("idiom"):
        from model.idiom import window_term
        Iterm, Iz = window_term(allout, [i.key for i in load_ensemble(regime).instruments], regime, w0, w1)
        R += setting["idiom"] * Iterm
    return {"R": R, "Fw": Fw, "H": H, "DS": DS, "G": G, "I": Iterm, "Iz": Iz, **extra, **{f"ret_{t}": r for t, r in ret.items()},
            "n_src": len(src_ids), "n_out": len(tr.out_notes), "interv": float(tr.intervened.mean()) if len(tr.intervened) else 0.0,
            "drop": float(np.mean([lab[0] == A.DROP for lab in tr.labels])) if tr.labels else 0.0}


# ------------------------------------------------------------ learner

def policy_terms(net, trajs: list[Trajectory], device, chunk: int = 512, return_logz: bool = False):
    """New masked log-prob of every recorded decision, over the STORED candidates and masks
    (float64). Returns (logp_new [D], decision -> trajectory index [D]). Differentiable."""
    import torch
    from model.features import collate
    exs, base = [], []
    for tr in trajs:
        base.append(len(exs))
        exs += tr.passes
    rows = np.concatenate([b + t.dec_pass for b, t in zip(base, trajs)])            # pass row per decision
    pos = np.concatenate([t.dec_pos for t in trajs])
    owner = np.concatenate([np.full(len(t.chosen), i) for i, t in enumerate(trajs)])
    K = max(len(c) for t in trajs for c in t.cands)
    cand = np.zeros((len(rows), K), np.int64)
    mask = np.zeros((len(rows), K), bool)
    d = 0
    for t in trajs:
        for c, m in zip(t.cands, t.masks):
            cand[d, :len(c)] = c; mask[d, :len(c)] = m
            d += 1
    chosen = np.concatenate([t.chosen for t in trajs])
    out = torch.empty(len(rows), dtype=torch.float64, device=device)
    logz = torch.empty(len(rows), dtype=torch.float64, device=device)     # log feasible mass (R34)
    for s in range(0, len(exs), chunk):
        sel = np.nonzero((rows >= s) & (rows < s + chunk))[0]
        if len(sel) == 0:
            continue
        b = {k: v.to(device) for k, v in collate(exs[s:s + chunk]).items()}
        o = net(b)
        r_ = torch.as_tensor(rows[sel] - s, device=device)
        p_ = torch.as_tensor(pos[sel], device=device)
        lp_part = torch.log_softmax(o["part"].double(), -1)[r_, p_]               # [n, 5]
        lp_oct = torch.log_softmax(o["octave"].double(), -1)[r_, p_]
        lp_real = torch.log_softmax(o["real"].double(), -1)[r_, p_]
        J = (lp_part[:, :4, None, None] + lp_oct[:, None, :, None] + lp_real[:, None, None, :]).flatten(1)
        assert J.shape[1] == N_JOINT, "configure(n_real) not called for this network"
        nP = b["part_mask"].sum(1)[r_]
        absent = torch.arange(N_JOINT, device=device)[None, :] // (N_OCT * N_REAL) >= nP[:, None]
        J = torch.cat([J.masked_fill(absent, -float("inf")), lp_part[:, DROP_SLOT:DROP_SLOT + 1]], 1)   # [n, N_JOINT+1]
        c_ = torch.as_tensor(cand[sel], device=device)
        m_ = torch.as_tensor(mask[sel], device=device)
        x = torch.gather(J, 1, c_).masked_fill(~m_, -float("inf"))
        ch = torch.as_tensor(chosen[sel], device=device)
        lz = torch.logsumexp(x, 1)
        out[torch.as_tensor(sel, device=device)] = x.gather(1, ch[:, None])[:, 0] - lz
        # R34b: log of the feasible share of the NON-DROP probability (feasibility given that the note is
        # played; DROP is excluded, so dropping cannot raise it). -inf where no non-DROP option is feasible.
        nd = x.masked_fill(c_ == DROP_ID, -float("inf"))
        logz[torch.as_tensor(sel, device=device)] = torch.logsumexp(nd, 1) - torch.logsumexp(J[:, :N_JOINT], 1)
    if return_logz:
        return out, torch.as_tensor(owner, device=device), logz
    return out, torch.as_tensor(owner, device=device)


def grpo_loss(net, ref, trajs, adv, device, clip=0.2, beta=0.02, feas=0.0):
    """feas > 0 (R34, exploratory): add feas * mean(-log feasible share of the non-DROP probability).
    The masked ratio and KL see only feasible options, so without it the probability on infeasible
    options gets no gradient at all. DROP is excluded from the share (R34b: rl-AZ, which counted DROP
    as feasible, learnt to drop 32-60% of notes)."""
    import torch
    lp_new, owner, logz = policy_terms(net, trajs, device, return_logz=True)
    with torch.no_grad():
        lp_ref, _ = policy_terms(ref, trajs, device)
    lp_old = torch.as_tensor(np.concatenate([t.logp_old for t in trajs]), device=device, dtype=torch.float64)
    A_ = torch.as_tensor(adv, device=device, dtype=lp_new.dtype)[owner]
    ratio = torch.exp(lp_new - lp_old)
    pg = -torch.minimum(ratio * A_, ratio.clamp(1 - clip, 1 + clip) * A_)
    d = lp_ref - lp_new
    kl = torch.exp(d) - d - 1                                   # k3 estimator, sampled under the stored masks
    ok = torch.isfinite(logz)
    feas_term = (-logz[ok]).sum() / max(1, len(logz))
    loss = pg.mean() + beta * kl.mean() + feas * feas_term
    return loss, {"loss": float(loss), "pg": float(pg.mean()), "kl": float(kl.mean()),
                  "feasible_share_played": float(torch.exp(logz[ok]).mean()) if ok.any() else 0.0,
                  "ratio_mean": float(ratio.mean()), "ratio_max": float(ratio.max()),
                  "clip_frac": float(((ratio - 1).abs() > clip).float().mean()), "n_decisions": len(lp_new)}


def accumulate_grads(net, ref, trajs, adv, device, clip, beta, micro: int, feas: float = 0.0) -> dict:
    """Backward of the token-mean GRPO loss over all trajectories, in micro-batches of trajectories
    (each weighted by its share of the decisions), so GPU memory is bounded. Same gradient as one batch."""
    n_dec = sum(len(t.chosen) for t in trajs)
    acc = defaultdict(float)
    for s0 in range(0, len(trajs), micro):
        mb = trajs[s0:s0 + micro]
        wmb = sum(len(t.chosen) for t in mb) / n_dec
        loss, st = grpo_loss(net, ref, mb, adv[s0:s0 + micro], device, clip, beta, feas)
        (loss * wmb).backward()
        for k, v in st.items():
            if k not in ("ratio_max", "n_decisions"):
                acc[k] += v * wmb
        acc["ratio_max"] = max(acc["ratio_max"], st["ratio_max"])
    acc["n_decisions"] = n_dec
    return dict(acc)


def advantages(rewards: np.ndarray, group: int) -> np.ndarray:
    R = rewards.reshape(-1, group)
    return ((R - R.mean(1, keepdims=True)) / (R.std(1, keepdims=True) + 0.05)).reshape(-1)


# ------------------------------------------------------------ CPU workers

_W: dict = {}


def _worker_init(ckpt_path, run_base, setting_name):
    import torch
    torch.set_num_threads(1)
    from model.net import Arranger
    ck = torch.load(ckpt_path, map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).eval()
    net.load_state_dict(ck["model"])
    configure(net.n_real)
    mvs = {m.key: m for m in attach_contexts(load_split("train"), run_base)}
    val = {m.key: m for m in load_split("val")}
    _W.update(net=net, version=-1, mvs=mvs, val=val, setting=SETTINGS[setting_name])
    _MF["on"] = bool(SETTINGS[setting_name].get("melody_first"))


def _sync(weights_path, version):
    import torch
    if _W["version"] != version:
        _W["net"].load_state_dict(torch.load(weights_path, map_location="cpu"))
        _W["version"] = version


def _rollout_job(job):
    key, regime, w0, G, seed, weights_path, version = job
    _sync(weights_path, version)
    rng = np.random.default_rng(seed)
    m = _W["mvs"][key]
    timing = Counter()
    trs = []
    for _ in range(G):
        tr = rollout(_W["net"], m, regime, w0, rng, timing=timing)
        tr.parts.update(window_reward(m, regime, w0, tr, _W["setting"]))
        tr.reward = tr.parts["R"]
        del tr.parts["_ctx_notes"]
        trs.append(tr)
    return trs, dict(timing)


def _val_job(job):
    """Greedy masked decode of one dev movement (model/decode.py, unchanged) + reduction metrics."""
    key, regime, weights_path, version = job[:4]
    melody_first = job[4] if len(job) > 4 else False
    _sync(weights_path, version)
    from arrangement.eval.record import make_score
    from arrangement.eval.reduction import reduction_metrics
    from model.decode import decode_movement
    m = _W["val"][key]
    ens = load_ensemble(regime)
    insts = [i.key for i in ens.instruments]
    inotes, com = decode_movement(_W["net"], "cpu", m.src, insts, ens, True, m.tpq, melody_first)
    out = make_score([(n, i.key) for n, i in zip(ens.part_names, ens.instruments)], A.expand(inotes))
    src = make_score([("Violin 1", "violin"), ("Violin 2", "violin"), ("Viola", "viola"), ("Violoncello", "cello")], m.src)
    red = reduction_metrics(out, src)
    real = Counter(n.real for n in inotes if n.part != A.DROP)
    km, nm_, _ = kept_weights(m, [i for i, q in enumerate(m.src) if q[2] > 0], A.expand(inotes), SETTINGS["M2"])
    fk = {}
    if regime in FK_REGIMES:                 # A3 detectors (model/dev_fk.py metrics)
        from model.dev_fk import metrics as fk_metrics
        r_ = fk_metrics(m, A.expand(inotes), "flute" if regime == "solo_flute" else "piano")
        fk = {f"fk_{k}": v for k, v in r_.items() if k in ("breaths", "dur_q", "longest_run_q", "harmony")}
        fk["fk_n_cut"] = real[A.CUT]
    return {"regime": regime, **fk, "n_in": len(inotes), "interventions": com.n_intervened,
            "drops": sum(n.part == A.DROP for n in inotes), "n_out": len(out.notes),
            "dur_out": float(sum(n[2] for n in out.notes)), "dur_src": float(sum(n[2] for n in m.src)),
            "n_repeat_ops": real[A.REPEAT] + real[A.TREMOLO], "n_kept_in": sum(real.values()),
            **{f"m_kept_{t}": km[t] for t in TIERS}, **{f"m_n_{t}": nm_[t] for t in TIERS}, **red}


def validate(pool, regimes, weights_path, version, n_val: int, melody_first: bool = False):
    keys = sorted(_val_keys())[:n_val]
    rows = pool.map(_val_job, [(k, r, weights_path, version, melody_first or r in FK_REGIMES) for r in regimes for k in keys],
                    chunksize=1)
    res = {}
    for r in regimes:
        rs = [x for x in rows if x["regime"] == r]
        n_in = sum(x["n_in"] for x in rs)
        res[f"val_{r}/intervention_rate"] = sum(x["interventions"] for x in rs) / n_in
        res[f"val_{r}/drop_rate"] = sum(x["drops"] for x in rs) / n_in
        for t in TIERS:
            res[f"val_{r}/retention_{t}"] = sum(x[f"retention__{t}__kept"] for x in rs) / max(1, sum(x[f"retention__{t}__n"] for x in rs))
        res[f"val_{r}/unneeded_ds_per_100"] = 100 * sum(x["unneeded_double_stops"] for x in rs) / max(1, sum(x["n_out"] for x in rs))
        # detector proxies at validation time (R36): catch note-splitting hacks within 100 steps
        res[f"val_{r}/note_ratio"] = sum(x["n_out"] for x in rs) / n_in
        res[f"val_{r}/mean_dur_ratio"] = (sum(x["dur_out"] for x in rs) / max(1, sum(x["n_out"] for x in rs))) / \
            (sum(x["dur_src"] for x in rs) / n_in)
        res[f"val_{r}/repeat_op_share"] = sum(x["n_repeat_ops"] for x in rs) / max(1, sum(x["n_kept_in"] for x in rs))
        if r in FK_REGIMES:
            res[f"val_{r}/cut_share"] = sum(x["fk_n_cut"] for x in rs) / max(1, sum(x["n_kept_in"] for x in rs))
            res[f"val_{r}/harmony"] = float(np.mean([x["fk_harmony"] for x in rs]))
            if r == "solo_flute":
                res[f"val_{r}/breaths_per_32q"] = 32 * sum(x["fk_breaths"] for x in rs) / sum(x["fk_dur_q"] for x in rs)
                res[f"val_{r}/longest_run_q_median"] = float(np.median([x["fk_longest_run_q"] for x in rs]))
        wm = SETTINGS["M2"]["w"]
        res[f"val_{r}/fidelity_M"] = (sum(wm[t] * sum(x[f"m_kept_{t}"] for x in rs) for t in TIERS)
                                      / max(1e-9, sum(wm[t] * sum(x[f"m_n_{t}"] for x in rs) for t in TIERS)))
        res[f"val_{r}/top_retention_M"] = sum(x["m_kept_top"] for x in rs) / max(1e-9, sum(x["m_n_top"] for x in rs))
        for s, w in SETTINGS.items():
            num = sum(w["w"][t] * sum(x[f"retention__{t}__kept"] for x in rs) for t in TIERS)
            den = sum(w["w"][t] * sum(x[f"retention__{t}__n"] for x in rs) for t in TIERS)
            res[f"val_{r}/weighted_fidelity_{s}"] = num / den
    return res


def _val_keys():
    return [json.loads(l)["key"] for l in open(ROOT / "model" / "data" / "val.jsonl")]


# ------------------------------------------------------------ lockstep engine (GPU forwards, CPU checker)

def _engine_worker(conn, ctx_run, setting_name):
    """Persistent worker: owns rollout states; does the checker, candidates and sampling (CPU).
    Protocol: ("init", jobs) -> list of first inputs; ("apply", {j: log-probs}) -> list of next inputs
    (None when that rollout is done); ("finish",) -> (trajectories with rewards, timing); ("stop",)."""
    mvs = {m.key: m for m in attach_contexts(load_split("train"), ctx_run)}
    setting = SETTINGS[setting_name]
    _MF["on"] = bool(setting.get("melody_first"))
    states, timing = [], Counter()
    while True:
        msg = conn.recv()
        if msg[0] == "init":
            timing = Counter()
            states = [RolloutState(mvs[k], r, w0, np.random.default_rng(seed), timing=timing) for k, r, w0, seed in msg[1]]
            conn.send([st.next_input() for st in states])
        elif msg[0] == "apply":
            out = []
            for j, st in enumerate(states):
                if j in msg[1]:
                    st.apply(*msg[1][j])
                    out.append(st.next_input())
                else:
                    out.append(None)
            conn.send(out)
        elif msg[0] == "finish":
            trs = []
            for st in states:
                tr = st.finish()
                tr.parts.update(window_reward(st.m, st.regime, st.w0, tr, setting))
                tr.reward = tr.parts["R"]
                del tr.parts["_ctx_notes"]
                trs.append(tr)
            conn.send((trs, dict(timing)))
        elif msg[0] == "stop":
            return


class LockstepEngine:
    def __init__(self, n_workers: int, ctx_run: str, setting_name: str):
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        self.conns, self.procs = [], []
        for _ in range(n_workers):
            a, b = ctx.Pipe()
            p = ctx.Process(target=_engine_worker, args=(b, ctx_run, setting_name), daemon=True)
            p.start()
            self.conns.append(a); self.procs.append(p)

    def run(self, net, device, jobs, chunk: int = 512):
        """jobs: [(key, regime, w0, seed)], one per trajectory, in order. Returns (trajectories in job
        order, timing). One batched forward per pass over every active rollout."""
        import torch
        from model.features import collate
        W = len(self.conns)
        parts = [list(range(i, len(jobs), W)) for i in range(W)]            # job indices per worker
        for c, ids in zip(self.conns, parts):
            c.send(("init", [jobs[i] for i in ids]))
        inputs = [c.recv() for c in self.conns]
        t_net, n_fw = 0.0, 0
        was_training = net.training
        net.eval()
        while True:
            flat = [(w, j, ex) for w, lst in enumerate(inputs) for j, ex in enumerate(lst) if ex is not None]
            if not flat:
                break
            res = [dict() for _ in range(W)]
            t0 = time.perf_counter()
            with torch.no_grad():
                for s0 in range(0, len(flat), chunk):
                    part = flat[s0:s0 + chunk]
                    b = {k: v.to(device) for k, v in collate([ex for _, _, ex in part]).items()}
                    out = net(b)
                    for i, (w, j, ex) in enumerate(part):
                        res[w][j] = _log_softmax_rows(out, i, len(ex["pitch"]))
                    n_fw += 1
            t_net += time.perf_counter() - t0
            for c, r in zip(self.conns, res):
                c.send(("apply", r))
            inputs = [c.recv() for c in self.conns]
        for c in self.conns:
            c.send(("finish",))
        trs = [None] * len(jobs)
        timing = Counter({"net_gpu_s": t_net, "forwards": n_fw})
        for c, ids in zip(self.conns, parts):
            ts, tm = c.recv()
            timing.update(tm)
            for i, t in zip(ids, ts):
                trs[i] = t
        net.train(was_training)
        return trs, timing

    def close(self):
        for c in self.conns:
            c.send(("stop",))
        for p in self.procs:
            p.join(timeout=10)


# ------------------------------------------------------------ commands

def cmd_contexts(a):
    """arranger greedy masked labels for every train / val movement and regime (the window contexts),
    plus the oracle-under-mask labels (model fallback) for control S."""
    import torch
    from model.decode import decode_movement
    from model.diagnose import decode_instrumented, oracle_labels
    from model.net import Arranger
    ck = torch.load(ROOT / "model" / "results" / a.run / "checkpoint.pt", map_location="cpu")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(1)      # many single-thread CPU processes beat a shared GPU here (30 s per decode)
    net = Arranger(**ck["cfg"]["net"]).to(device).eval()
    net.load_state_dict(ck["model"])
    configure(net.n_real)
    ranges = A.load_ranges()
    out = {}
    mvs = load_split(a.split)[a.shard::a.nshards][: a.limit]
    for m in mvs:
        out[m.key] = {"greedy": {}, "oracle": {}}
        for regime in a.regimes:
            ens = load_ensemble(regime)
            insts = [i.key for i in ens.instruments]
            inotes, _ = decode_movement(net, device, m.src, insts, ens, True, m.tpq, a.melody_first)
            out[m.key]["greedy"][regime] = [(n.part, n.octave, n.real) for n in inotes]
            if a.split == "train" and not a.greedy_only:
                inotes, _ = decode_instrumented(net, device, m.src, insts, ens, m.tpq, oracle_labels(m.src, regime, ranges))
                out[m.key]["oracle"][regime] = [(n.part, n.octave, n.real) for n in inotes]
        print(m.key[:60], flush=True)
    (RL / "contexts").mkdir(parents=True, exist_ok=True)
    pickle.dump(out, open(RL / "contexts" / f"{a.out_name or a.run}__{a.split}.{a.shard}.pkl", "wb"))


def cmd_train(a):
    import multiprocessing as mp
    import torch
    from model.net import Arranger
    setting = SETTINGS[a.setting]
    od = RL / a.run_name
    od.mkdir(parents=True, exist_ok=True)
    base_ck = ROOT / "model" / "results" / a.base / "checkpoint.pt"
    ck = torch.load(base_ck, map_location="cpu")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = Arranger(**ck["cfg"]["net"]).to(device)
    net.load_state_dict(ck["model"])
    configure(net.n_real)
    ref = Arranger(**ck["cfg"]["net"]).to(device).eval()
    ref.load_state_dict(ck["model"])
    for p_ in ref.parameters():
        p_.requires_grad_(False)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.0)
    cfg = {**vars(a), "setting_values": setting, "rho": RHO, "n_real": N_REAL, "cand_mass": CAND_MASS, "cand_max": CAND_MAX,
           "base_checkpoint": str(base_ck), "base_step": ck["step"]}
    cfg.pop("func", None)
    (od / "config.json").write_text(json.dumps(cfg, indent=1, default=str))
    weights = Path("/dev/shm") / f"grpo_{a.run_name}_{os.getpid()}.pt"
    torch.save({k: v.cpu() for k, v in net.state_dict().items()}, weights)
    version = 0
    mvs = attach_contexts(load_split("train"), a.ctx_run or a.base)
    jobs_all = [(m.key, r, w0) for m in mvs for r in a.regimes if r in m.ctx for w0 in windows(m, 384)]
    print(f"{len(jobs_all)} train windows", flush=True)
    rng = random.Random(a.seed)
    os.environ.setdefault("WANDB_MODE", "online" if os.environ.get("WANDB_API_KEY") else "offline")
    os.environ.setdefault("WANDB_DIR", str(ROOT / "model"))
    import wandb
    wb = wandb.init(project="playable-arrangement", name=a.run_name, config=cfg, mode=os.environ["WANDB_MODE"])
    log_f = open(od / "log.csv", "w")
    header = None
    gpu_log = open(od / "gpu.csv", "w")
    import subprocess
    import threading
    stop = threading.Event()

    def gpu_sampler():
        while not stop.is_set():
            q = subprocess.run(["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True).stdout.strip().replace("\n", ";")
            gpu_log.write(f"{time.time():.0f},{q}\n"); gpu_log.flush()
            stop.wait(10)
    threading.Thread(target=gpu_sampler, daemon=True).start()
    ctx = mp.get_context("fork")
    engine = LockstepEngine(a.workers, a.ctx_run or a.base, a.setting) if a.engine == "lockstep" else None
    n_pool = a.val_workers if engine is not None else a.workers
    with ctx.Pool(n_pool, initializer=_worker_init, initargs=(str(base_ck), a.ctx_run or a.base, a.setting)) as pool:
        t_start = time.time()
        for step in range(a.steps + 1):
            row = {"step": step}
            if step % a.val_every == 0:
                tv = time.time()
                row.update(validate(pool, a.regimes, str(weights), version, a.n_val))
                row["time/val_s"] = time.time() - tv
                torch.save({"model": net.state_dict(), "cfg": {**ck["cfg"], "run_name": a.run_name}, "step": step, "rl": cfg},
                           od / "checkpoint.pt")
                if step == a.steps:       # final validation: log it (it was silently dropped before)
                    wb.log(row, step=step)
                    if header is not None:
                        log_f.write(",".join(str(row.get(h, "")) for h in header) + "\n"); log_f.flush()
                    (od / "final_val.json").write_text(json.dumps(row, indent=1))
                    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
                    break
            tr0 = time.time()
            batch = rng.sample(jobs_all, a.windows)
            if engine is not None:      # lockstep: GPU forwards, CPU checker; samples of a window contiguous
                ljobs = [(k, r, w0, rng.randrange(1 << 30)) for k, r, w0 in batch for _ in range(a.group)]
                trajs, timing = engine.run(net, device, ljobs)
            else:
                jobs = [(k, r, w0, a.group, rng.randrange(1 << 30), str(weights), version) for k, r, w0 in batch]
                res = pool.map(_rollout_job, jobs, chunksize=1)
                trajs = [t for trs, _ in res for t in trs]
                timing = Counter()
                for _, tm in res:
                    timing.update(tm)
            t_roll = time.time() - tr0
            rewards = np.array([t.reward for t in trajs])
            adv = advantages(rewards, a.group)
            tu = time.time()
            stats = {}
            for _ in range(a.epochs):
                opt.zero_grad(set_to_none=True)
                stats = accumulate_grads(net, ref, trajs, adv, device, a.clip, a.beta, a.micro, a.feas)
                gn = torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
            torch.save({k: v.cpu() for k, v in net.state_dict().items()}, weights)
            version += 1
            t_upd = time.time() - tu
            parts = defaultdict(list)
            for t in trajs:
                for k, v in t.parts.items():
                    if isinstance(v, (int, float)) and not k.startswith("_"):
                        parts[k].append(v)
            row.update({f"train/{k}": float(np.nanmean(v)) if not np.all(np.isnan(v)) else float("nan") for k, v in parts.items()})
            row.update({f"train/{k}": v for k, v in stats.items()})
            row.update({"train/grad_norm": float(gn), "train/reward_std_within_group": float(rewards.reshape(-1, a.group).std(1).mean()),
                        "time/rollout_s": t_roll, "time/update_s": t_upd, "time/elapsed_s": time.time() - t_start,
                        "time/worker_net_s": timing.get("net_s", 0.0), "time/net_gpu_s": timing.get("net_gpu_s", 0.0),
                        "time/forwards": timing.get("forwards", 0), "time/worker_checker_s": timing["checker_s"],
                        "time/worker_apply_s": timing.get("apply_s", 0.0), "time/worker_rollout_s": timing.get("rollout_s", 0.0), "time/probes_per_note": timing["probes"] / max(1, timing["notes"]),
                        "time/candidates_per_decision": timing["probes"] / max(1, sum(len(t.chosen) for t in trajs))})
            wb.log(row, step=step)
            if header is None:
                header = list(row.keys())
                log_f.write(",".join(header) + "\n")
            log_f.write(",".join(str(row.get(h, "")) for h in header) + "\n"); log_f.flush()
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    if engine is not None:
        engine.close()
    stop.set()
    wb.finish()
    weights.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("contexts")
    c.add_argument("--run", default="arranger-v2b")
    c.add_argument("--split", default="train")
    c.add_argument("--shard", type=int, default=0)
    c.add_argument("--nshards", type=int, default=1)
    c.add_argument("--out-name", default=None)
    c.add_argument("--limit", type=int, default=None)
    c.add_argument("--greedy-only", action="store_true", help="skip the oracle labels (RL contexts only)")
    c.add_argument("--regimes", nargs="+", default=list(REGIMES))
    c.add_argument("--melody-first", action="store_true", help="decode v3 contexts (as the F/K systems are decoded)")
    t = sub.add_parser("train")
    t.add_argument("--setting", default="C", choices=list(SETTINGS))
    t.add_argument("--run-name", default=None)
    t.add_argument("--base", default="arranger-v2b")
    t.add_argument("--steps", type=int, default=3000)
    t.add_argument("--windows", type=int, default=32)
    t.add_argument("--group", type=int, default=8)
    t.add_argument("--epochs", type=int, default=2)
    t.add_argument("--micro", type=int, default=16, help="trajectories per gradient-accumulation micro-batch")
    t.add_argument("--engine", default="lockstep", choices=["lockstep", "pool"],
                   help="lockstep: batched GPU forwards + CPU checker workers; pool: whole rollouts on CPU workers")
    t.add_argument("--val-workers", type=int, default=12, help="CPU workers for validation decodes (lockstep engine)")
    t.add_argument("--lr", type=float, default=1e-5)
    t.add_argument("--clip", type=float, default=0.2)
    t.add_argument("--beta", type=float, default=0.02)
    t.add_argument("--feas", type=float, default=0.0, help="R34 (exploratory): weight of -log feasible mass")
    t.add_argument("--workers", type=int, default=48)
    t.add_argument("--val-every", type=int, default=100)
    t.add_argument("--n-val", type=int, default=20)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--ctx-run", default=None, help="contexts file prefix (default: --base)")
    t.add_argument("--regimes", nargs="+", default=list(REGIMES), help="e.g. solo_flute or piano (Amendment A)")
    a = ap.parse_args(argv)
    if a.cmd == "contexts":
        cmd_contexts(a)
    else:
        a.run_name = a.run_name or f"rl-{a.setting}"
        cmd_train(a)


if __name__ == "__main__":
    main()
