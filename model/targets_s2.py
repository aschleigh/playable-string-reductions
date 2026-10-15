"""S2 supervised targets (REVIEW R44): the true reduction with merged double stops resolved the way the
user specified (BLOCK4 decisions 2-3): keep the more important voice, move or re-voice the other, and drop
an inner voice rather than keep a hard double stop.

    python -m model.targets_s2 [--regimes trio duo] [--workers 32]     -> model/results/rl/targets_s2.pkl

Per movement and regime. Notes are visited in time order, then by voice tier of the source (top, bass,
inner), then by pitch, highest first. Each takes the first acceptable option:
  1. its true part and octave (the training-target reduction: Vn1+Vn2 -> violin etc.);
  2. another part at the same pitch, nearest register first;
  3. an octave or two away (+-12, +-24), its own part first, then the others;
     (a note moved into the cello must stay below 6th position, <= G4 (U20); higher -> the octave below)
  4. top or bass notes only: its true part even with a double stop (the melody and bass are not dropped);
  5. otherwise DROP.
Acceptable = feasible under the frozen checker (the decoder's Committer: checker-v5, unisons merged) AND,
for options 1-3, creates no unneeded double stop: no other note of that output part sounds during the
note unless they all come from one source part and sound together there (a double stop the source has).
Labels are plain realisation. Output: {key: {regime: [(part, octave, realisation)] in decode order}}.
"""
from __future__ import annotations

import argparse
import pickle
from collections import Counter, defaultdict
from multiprocessing import Pool

import model.augment as A
from arrangement.instruments import load_ensemble
from model.decode import TIER_RANK, Committer
from model.diagnose import oracle_labels
from model.grpo import RL, load_split

REGIMES = ("trio", "duo")
CELLO_MOVED_MAX = 67   # PLACEHOLDER (U20): G4, about the top of 5th position on the A string [User: "6th position"]


def _overlaps(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def build(m, regime, ranges):
    ens = load_ensemble(regime)
    insts = ens.instruments
    labs = oracle_labels(m.src, regime, ranges)
    inotes = [A.INote(o, d, x, src=p) for p, o, d, x in m.src]
    com = Committer(ens, m.tpq, True, max((n.dur for n in inotes), default=1))
    placed = defaultdict(list)                       # output part -> [(on, end, source index)]
    order = sorted(range(len(m.src)), key=lambda i: (m.src[i][1], TIER_RANK[m.tiers[i]], -m.src[i][3]))
    stats = Counter()

    def no_new_double(i, q):
        o, d = m.src[i][1], m.src[i][2]
        hits = [j for (a, b, j) in placed[q] if _overlaps(o, o + d, a, b)]
        if not hits:
            return True
        grp = hits + [i]                             # a double stop the source has: one source part, together
        return len({m.src[j][0] for j in grp}) == 1 and max(m.src[j][1] for j in grp) < min(m.src[j][1] + m.src[j][2] for j in grp)

    def in_range(x, q):
        return insts[q].low <= x <= insts[q].high

    def comfortable(x, q, kind):
        # user (2026-10-15): when the cello takes over another part's material, not into 6th position or above;
        # take it down an octave instead. The cello's own source notes are not restricted.
        return not (insts[q].key == "cello" and kind != "kept" and x > CELLO_MOVED_MAX)

    for i in order:
        p0, oc0 = labs[i]
        x = m.src[i][3]
        tier = m.tiers[i]
        opts = []
        if p0 != A.DROP:
            opts.append((p0, oc0, "kept", True))
        others = sorted((q for q in range(len(insts)) if q != p0),
                        key=lambda q: (max(insts[q].low - x, 0, x - insts[q].high), q))
        opts += [(q, 0, "moved", True) for q in others]
        own = [p0] if p0 != A.DROP else []
        for s in (-12, 12, -24, 24):
            opts += [(q, s, "octave", True) for q in own + others]
        if tier in ("top", "bass") and p0 != A.DROP:
            opts.append((p0, oc0, "kept_double", False))
        chosen = None
        for q, s, kind, need_single in opts:
            if s not in A.OCTAVES or not in_range(x + s, q) or not comfortable(x + s, q, kind):
                continue
            if need_single and not no_new_double(i, q):
                continue
            if com.try_commit(i, inotes, q, s, A.PLAIN):
                chosen = (q, s, kind)
                break
        if chosen is None:
            inotes[i].part = A.DROP
            stats[f"drop_{tier}"] += 1
            continue
        q, s, kind = chosen
        stats[f"{kind}_{tier}"] += 1
        if not inotes[i].merged:
            placed[q].append((m.src[i][1], m.src[i][1] + m.src[i][2], i))
    return [(n.part, n.octave, n.real) for n in inotes], stats


def _job(args):
    m, regimes = args
    ranges = A.load_ranges()
    out, st = {}, Counter()
    for r in regimes:
        out[r], s = build(m, r, ranges)
        st.update({f"{r}:{k}": v for k, v in s.items()})
    return m.key, out, st


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", nargs="+", default=list(REGIMES))
    ap.add_argument("--split", default="train")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    mvs = load_split(a.split)[: a.limit]
    with Pool(a.workers) as pool:
        res = pool.map(_job, [(m, a.regimes) for m in mvs], chunksize=1)
    tot = Counter()
    for _, _, st in res:
        tot.update(st)
    pickle.dump({k: o for k, o, _ in res}, open(RL / f"targets_s2__{a.split}.pkl", "wb"))
    for r in a.regimes:
        n = sum(v for k, v in tot.items() if k.startswith(r + ":"))
        print(r, {k.split(":")[1]: f"{v} ({100 * v / n:.1f}%)" for k, v in sorted(tot.items()) if k.startswith(r + ":")})


if __name__ == "__main__":
    main()
