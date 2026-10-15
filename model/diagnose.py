"""Block 4, Step 1 diagnostics. Read-only measurement: no training, no model or checker change.

    python -m model.diagnose decode --regime trio --mode arranger|oracle --shard S --nshards N   (GPU)
    python -m model.diagnose cpu --regime trio|duo|quartet                                       (CPU)
    python -m model.diagnose report [--workers N]

1a  Oracle under the mask. The TRUE target arrangement of each evaluation movement (the
    training-target reduction: Vn1+Vn2 -> violin etc., nearest-octave range fit, unison
    duplicates dropped, every note plain; quartet = the source itself) is pushed through the
    frozen checker-v4 mask with GrowingChecker, and the result scored with the frozen harness.
      oracle             the true target, unmasked
      oracle_mask_drop   time order (highest pitch first); true option, else DROP
      oracle_mask_repair same order; true option, else the Ou-repair order (other parts by
                         register, octave, both), else DROP (decoding/repair.py options())
      oracle_mask_model  exactly the masked decoding loop (model confidence order, model
                         features from the committed state), except that each note tries its
                         true option first, then the model's ranked joint options
1b  Double-stop provenance. Every output-part onset where >= 2 notes sound is classified:
      op      the `double` realisation op (one input note -> two output notes)
      merge   notes from >= 2 different source parts in one output part
      source  one source part, the notes already sound together in the source
      other   one source part, not together in the source
1c  Mask interventions in arranger_masked, re-decoded with instrumentation (the re-decode
    must reproduce the stored records exactly; checked and reported): the blocking checks
    of the top joint option, what the fallback changed, where interventions fall, which
    voices are dropped, and an accounting split of the fidelity cost into DROP and
    alternative fallbacks (counterfactual records with those notes restored to the top
    option, scored with the frozen harness; unplayable by construction, accounting only).

Voice tiers (source, per note): top = no source note sounding at its onset is higher;
bass = none is lower (and it is not alone); inner = the rest. A note alone is top. Unisons
tie upward (both top). Voice crossings are handled by sounding pitch, not by part.

Outputs: model/results/diagnostics/ (records/, per-note pickles, report.json, REPORT.md).
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from collections import Counter, defaultdict
from fractions import Fraction as F
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import model.augment as A  # noqa: E402
from arrangement.eval.record import ArrangementRecord, load, make_score, save  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402

OUT = ROOT / "model" / "results" / "diagnostics"
REC = ROOT / "headroom" / "data" / "records"
RUN = ROOT / "model" / "results" / "arranger-v1"
REFERENCE = {"trio": [[0], [2], [3]], "duo": [[0], [3]], "quartet": [[0], [1], [2], [3]]}
TPQ_BASE = 720720
SRC_NAMES = ["Vn1", "Vn2", "Va", "Vc"]


# ------------------------------------------------------------ shared helpers

def sorted_source(r):
    """Input-note order used by model/decode.py (stable sort of the source notes)."""
    return sorted(r.source.notes, key=lambda n: (n[1], n[3], n[2]))


def tpq_of(r) -> int:
    return TPQ_BASE * math.lcm(1, *{x.denominator for n in r.source.notes for x in (n[1], n[2])})


def oracle_labels(src, regime, ranges):
    """[part, octave] per input note: the training-target reduction (augment.make_example, augment=False)."""
    insts, pmap = A.ENSEMBLES[regime]
    labs = []
    for sp, o, d, x in src:
        p, oc = pmap[sp], 0
        lo, hi = ranges[insts[p]]
        if not lo <= x <= hi:
            for extra in sorted((-24, -12, 12, 24), key=abs):
                if lo <= x + extra <= hi:
                    oc = extra
                    break
            else:
                p = A.DROP
        labs.append([p, oc])
    seen = set()
    for i in sorted(range(len(src)), key=lambda i: -src[i][2]):   # unison duplicates: keep the longest
        p, oc = labs[i]
        if p == A.DROP:
            continue
        k = (p, src[i][1], src[i][3] + oc)
        if k in seen:
            labs[i][0] = A.DROP
        else:
            seen.add(k)
    return labs


def voice_tiers(src) -> list[str]:
    on = np.array([float(n[1]) for n in src]); en = on + np.array([float(n[2]) for n in src])
    px = np.array([n[3] for n in src])
    order = np.argsort(on, kind="stable")
    out = []
    for i in range(len(src)):
        t = on[i]
        snd = (on <= t) & (en > t) if en[i] > on[i] else (on == t)
        snd[i] = True
        others = px[snd & (np.arange(len(src)) != i)]
        if len(others) == 0 or (others <= px[i]).all():
            out.append("top")
        elif (others > px[i]).all():
            out.append("bass")
        else:
            out.append("inner")
    del order
    return out


def expand_tracked(inotes):
    """augment.expand plus provenance: (part, onset, dur, pitch, input index, op)."""
    out, groups = [], {}
    for i, n in enumerate(inotes):
        if n.part == A.DROP:
            continue
        p = n.pitch + n.octave
        if n.real == A.ARPEGGIATE:
            groups.setdefault((n.part, n.onset, n.dur), []).append(i)
        elif n.real in (A.REPEAT, A.TREMOLO):
            sub = F(1, 2) if n.real == A.REPEAT else F(1, 4)
            if n.dur < 2 * sub:
                out += [(n.part, n.onset, n.dur / 2, p, i, "rep"), (n.part, n.onset + n.dur / 2, n.dur / 2, p, i, "rep")]
            else:
                k = int(n.dur // sub)
                out += [(n.part, n.onset + j * sub, sub, p, i, "rep") for j in range(k - 1)]
                out.append((n.part, n.onset + (k - 1) * sub, n.dur - (k - 1) * sub, p, i, "rep"))
        elif n.real == A.DOUBLE:
            out += [(n.part, n.onset, n.dur, p, i, "double"), (n.part, n.onset, n.dur, p + 12, i, "double")]
        else:
            out.append((n.part, n.onset, n.dur, p, i, "plain"))
    for (part, o, d), g in groups.items():
        g = sorted(g, key=lambda i: inotes[i].pitch + inotes[i].octave)
        k = len(g)
        out += [(part, o + j * d / k, d / k, inotes[i].pitch + inotes[i].octave, i, "arp") for j, i in enumerate(g)]
    return out


def make_record(base, system, regime, ens, notes):
    parts = [(n, i.key) for n, i in zip(ens.part_names, ens.instruments)]
    return ArrangementRecord(system=system, system_version="diagnostic", seed=None, input_id=base.input_id,
                             ensemble=regime, source=base.source, output=make_score(parts, notes), bars=base.bars,
                             reference_source_parts=tuple(tuple(x) for x in REFERENCE[regime]), meta=base.meta)


def base_records(regime):
    if regime == "quartet":
        return load(REC / "continuity__quartet.jsonl")
    return load(REC / f"continuity__{regime}.jsonl")


# ------------------------------------------------------------ instrumented masked decoding (GPU)

def _committer_cls():
    from model.decode import Committer

    class ICommitter(Committer):
        """Committer that remembers which checks the last failed attempt hit."""
        last: tuple = ()

        def _add(self, notes):
            slots, bad = [], False
            self.last = ()
            for part, o, d, x in notes:
                try:
                    on, en = self._t(o), self._t(o + d)
                except ValueError:
                    self.last, bad = ("off_grid",), True
                    break
                if not 0 <= x <= 127:
                    self.last, bad = ("pitch_bounds",), True
                    break
                i, added = self.ck.add(on, en, x, part)
                slots.append(i)
                if added:
                    self.last, bad = tuple(sorted({v.check for v in added})), True
                    break
            return slots, bad
    return ICommitter


def decode_instrumented(net, device, src, insts, ens, tpq, oracle=None):
    """model/decode.py decode_movement (masked), plus per-note records. oracle = [part, octave]
    per input note: tried first (plain), then the model's ranked joint options."""
    import torch
    from model.features import MAX_NOTES, collate, encode
    from model.net import PART_DROP
    inotes = [A.INote(o, d, x, src=sp) for sp, o, d, x in src]
    decided = np.zeros(len(inotes), bool)
    com = _committer_cls()(ens, tpq, True, max((n.dur for n in inotes), default=F(1)))
    info = [None] * len(inotes)
    end = max((n.onset for n in inotes), default=F(0))
    w0, P, ov = F(0), len(insts), A.OCTAVES
    while w0 <= end:
        wl, cl = A.WINDOW, A.CONTEXT
        while True:
            win = [i for i, n in enumerate(inotes) if w0 - cl <= n.onset < w0 + wl]
            if len(win) <= MAX_NOTES or wl <= F(1, 4):
                break
            wl, cl = wl / 2, cl / 2
        com.n_shrunk += wl < A.WINDOW
        win = win[:MAX_NOTES]
        npass = 0
        while True:
            todo = [i for i in win if not decided[i] and inotes[i].onset >= w0]
            if not todo:
                break
            sub = [inotes[i] for i in win]
            for i, n in zip(win, sub):
                n.context = n.onset < w0
            reveal = np.array([decided[i] for i in win], bool)
            b = {k: v.to(device) for k, v in collate([encode(sub, insts, w0, reveal)]).items()}
            with torch.no_grad():
                out = net(b)
            pp = torch.softmax(out["part"][0], -1).cpu().numpy()
            po = torch.softmax(out["octave"][0], -1).cpu().numpy()
            pr = torch.softmax(out["real"][0], -1).cpu().numpy()
            pos = {i: k for k, i in enumerate(win)}
            conf = sorted(todo, key=lambda i: -(pp[pos[i]].max() * po[pos[i]].max() * pr[pos[i]].max()))
            k = math.ceil(len(todo) / 2)
            part_ids = list(range(P)) + [PART_DROP]
            for i in conf[:k]:
                j = pos[i]
                opts = sorted(((pp[j][pc] * po[j][o] * pr[j][r], pc, o, r)
                               for pc in part_ids for o in range(len(ov)) for r in range(5)), reverse=True)
                if oracle is not None:
                    tp, toc = oracle[i]
                    first = (1.0, PART_DROP if tp == A.DROP else tp, ov.index(toc), A.PLAIN)
                    opts = [first] + [x for x in opts if x[1:] != first[1:]]
                top = opts[0]
                rec = {"top": top[1:], "p_top": float(top[0]), "blocked": None, "n_failed": 0,
                       "chosen": None, "w0": float(w0), "pass": npass}
                for rank, (_, pc, o, r) in enumerate(opts):
                    if pc == PART_DROP:
                        com.try_commit(i, inotes, A.DROP, 0, A.PLAIN)
                        rec["chosen"] = (pc, o, r)
                        break
                    if com.try_commit(i, inotes, pc, ov[o], r):
                        rec["chosen"] = (pc, o, r)
                        break
                    if rank == 0:
                        rec["blocked"] = com.last
                    rec["n_failed"] += 1
                    com.n_fallback += 1
                info[i] = rec
                decided[i] = True
            npass += 1
        w0 += wl
    return inotes, info


def cmd_decode(a):
    import torch
    from model.net import Arranger
    ck = torch.load(RUN / "checkpoint.pt", map_location="cpu")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net = Arranger(**ck["cfg"]["net"]).to(device).eval()
    net.load_state_dict(ck["model"])
    ens = load_ensemble(a.regime)
    insts = [i.key for i in ens.instruments]
    assert insts == A.ENSEMBLES[a.regime][0], (insts, A.ENSEMBLES[a.regime][0])
    ranges = A.load_ranges()
    rows = []
    for r in base_records(a.regime)[a.shard::a.nshards]:
        src = sorted_source(r)
        orc = oracle_labels(src, a.regime, ranges) if a.mode == "oracle" else None
        inotes, info = decode_instrumented(net, device, src, insts, ens, tpq_of(r), orc)
        rows.append({"input_id": r.input_id,
                     "labels": [(n.part, n.octave, n.real) for n in inotes], "info": info})
        print(a.mode, a.regime, r.input_id[:50], flush=True)
    d = OUT / "decode"
    d.mkdir(parents=True, exist_ok=True)
    pickle.dump(rows, open(d / f"{a.mode}__{a.regime}.{a.shard}.pkl", "wb"))


# ------------------------------------------------------------ CPU oracle variants

def _oracle_cpu(job):
    regime, r = job
    from decoding.repair import options
    from model.decode import Committer
    ens = load_ensemble(regime)
    ranges = A.load_ranges()
    src = sorted_source(r)
    labs = oracle_labels(src, regime, ranges)
    out = {}
    plain = [A.INote(o, d, x, part=p, octave=oc) for (_, o, d, x), (p, oc) in zip(src, labs)]
    out["oracle"] = A.expand(plain)
    order = sorted(range(len(src)), key=lambda i: (src[i][1], -src[i][3], src[i][2]))
    stats = {}
    for mode in ("drop", "repair"):
        inotes = [A.INote(o, d, x) for _, o, d, x in src]
        com = Committer(ens, tpq_of(r), True, max((n.dur for n in inotes), default=F(1)))
        c = Counter()
        for i in order:
            p, oc = labs[i]
            if p == A.DROP:
                inotes[i].part = A.DROP
                c["target_drop"] += 1
                continue
            if com.try_commit(i, inotes, p, oc, A.PLAIN):
                c["kept"] += 1
                continue
            c["blocked"] += 1
            if mode == "repair":
                x = inotes[i].pitch
                for q, y, kind in options(x + oc, p, ens):
                    if kind == "kept" or (y - x) not in A.OCTAVES:
                        continue
                    if com.try_commit(i, inotes, q, y - x, A.PLAIN):
                        c[f"rerouted_{kind}"] += 1
                        break
                else:
                    inotes[i].part = A.DROP
                    c["dropped"] += 1
            else:
                inotes[i].part = A.DROP
                c["dropped"] += 1
        out[f"oracle_mask_{mode}"] = A.expand(inotes)
        out[f"labels_{mode}"] = [(n.part, n.octave, n.real) for n in inotes]
        stats[mode] = dict(c)
    out["labels_oracle"] = [(n.part, n.octave, n.real) for n in plain]
    return r.input_id, out, stats


def cmd_cpu(a):
    base = base_records(a.regime)
    ens = load_ensemble(a.regime)
    with Pool(a.workers) as pool:
        res = pool.map(_oracle_cpu, [(a.regime, r) for r in base], chunksize=1)
    by = {r.input_id: r for r in base}
    rd = OUT / "records"
    rd.mkdir(parents=True, exist_ok=True)
    for sy in ("oracle", "oracle_mask_drop", "oracle_mask_repair"):
        save([make_record(by[k], sy, a.regime, ens, out[sy]) for k, out, _ in res], rd / f"{sy}__{a.regime}.jsonl")
    pickle.dump({k: {m: out[f"labels_{m}"] for m in ("oracle", "drop", "repair")} for k, out, _ in res},
                open(OUT / f"oracle_cpu_labels__{a.regime}.pkl", "wb"))
    tot = {m: Counter() for m in ("drop", "repair")}
    for _, _, st in res:
        for m in st:
            tot[m].update(st[m])
    (OUT / f"oracle_cpu_stats__{a.regime}.json").write_text(json.dumps({m: dict(c) for m, c in tot.items()}, indent=1))
    print(a.regime, {m: dict(c) for m, c in tot.items()})


# ------------------------------------------------------------ analysis

def load_decode(mode, regime):
    rows = []
    for p in sorted((OUT / "decode").glob(f"{mode}__{regime}.*.pkl")):
        rows += pickle.load(open(p, "rb"))
    return {r["input_id"]: r for r in rows}


def inotes_from(src, labels):
    return [A.INote(o, d, x, part=p, octave=oc, real=re) for (_, o, d, x), (p, oc, re) in zip(src, labels)]


def double_stops(tracked, src, n_parts):
    """Classify every output-part onset with >= 2 sounding notes. Returns Counter by class and by part.
    Sweep over onsets per part (notes sorted by onset; the sounding set drops notes that have ended)."""
    cls, by_part = Counter(), Counter()
    per_part = defaultdict(list)
    for t in tracked:
        if t[2] > 0:
            per_part[t[0]].append(t)
    for p, ns in per_part.items():
        ns.sort(key=lambda n: n[1])
        active, k = [], 0
        for t in sorted({n[1] for n in ns}):
            while k < len(ns) and ns[k][1] <= t:
                active.append(ns[k]); k += 1
            active = [n for n in active if n[1] + n[2] > t]
            S = active
            if len(S) < 2:
                continue
            idx = {n[4] for n in S}
            sps = {src[i][0] for i in idx}
            if any(n[5] == "double" for n in S) and len(idx) == 1:
                c = "op"
            elif len(sps) >= 2:
                c = "merge"
            else:
                iv = [(src[i][1], src[i][1] + src[i][2]) for i in idx]
                together = max(a for a, _ in iv) < min(b for _, b in iv)
                c = "source" if together else "other"
            cls[c] += 1
            by_part[(p, c)] += 1
    return cls, by_part


def _ds_job(job):
    regime, r, label_sets = job
    ens_n = len(load_ensemble(regime).instruments)
    src = sorted_source(r)
    tiers = voice_tiers(src)
    out = {}
    for sy, labels in label_sets.items():
        tr = expand_tracked(inotes_from(src, labels))
        c, bp = double_stops(tr, src, ens_n)
        k_, n_ = retention_by_tier(src, [t[:4] for t in tr], tiers)
        out[sy] = (len(tr), c, bp, k_, n_)
    return out


def bar_index(bars, t):
    starts = [b[0] for b in bars]
    import bisect
    return max(0, bisect.bisect_right(starts, t) - 1)


def analyse_interventions(regime, base, dec, stored=None):
    """1c on arranger_masked (dec = instrumented re-decode). Returns dict + counterfactual note lists."""
    res = {"n_notes": 0, "n_top_drop": 0, "n_intervened": 0, "n_failed_options": 0}
    blocked, outcome = Counter(), Counter()
    by_poly, by_poly_n = Counter(), Counter()
    tier_n, tier_drop, tier_drop_int = Counter(), Counter(), Counter()
    sp_n, sp_drop, sp_drop_int = Counter(), Counter(), Counter()
    bar_int, bar_notes = [], []
    reproduced = mism = 0
    cf = {"cf_undo_drops": [], "cf_undo_alts": [], "cf_undo_all": []}
    ens = load_ensemble(regime)
    for r in base:
        d = dec[r.input_id]
        src = sorted_source(r)
        inotes = inotes_from(src, d["labels"])
        if stored is not None:
            if sorted(A.expand(inotes)) == sorted(stored[r.input_id]):
                reproduced += 1
            else:
                mism += 1
        tiers = voice_tiers(src)
        on = np.array([float(n[1]) for n in src]); en = on + np.array([float(n[2]) for n in src])
        nb = len(r.bars)
        bi, bn = np.zeros(nb), np.zeros(nb)
        undo_d, undo_a = [], []
        for i, rec in enumerate(d["info"]):
            res["n_notes"] += 1
            poly = int(((on <= on[i]) & (en > on[i])).sum()) if en[i] > on[i] else 1
            pb = min(poly, 8)
            by_poly_n[pb] += 1
            tier_n[tiers[i]] += 1
            sp_n[src[i][0]] += 1
            b = bar_index(r.bars, src[i][1]); bn[b] += 1
            dropped = d["labels"][i][0] == A.DROP
            if dropped:
                tier_drop[tiers[i]] += 1; sp_drop[src[i][0]] += 1
            top, ch = tuple(rec["top"]), tuple(rec["chosen"])
            P = 4                # model.net.PART_DROP (= MAX_PARTS), not the ensemble size
            if top[0] == P:      # the model itself chose DROP
                res["n_top_drop"] += 1
                continue
            if rec["n_failed"] == 0:
                continue
            res["n_intervened"] += 1
            res["n_failed_options"] += rec["n_failed"]
            by_poly[pb] += 1
            bi[b] += 1
            for c in rec["blocked"] or ("?",):
                blocked[c] += 1
            if ch[0] == P:
                outcome["drop"] += 1
                tier_drop_int[tiers[i]] += 1; sp_drop_int[src[i][0]] += 1
                undo_d.append(i)
            else:
                k = "+".join(n for n, a_, b_ in (("part", top[0], ch[0]), ("octave", top[1], ch[1]),
                                                 ("realisation", top[2], ch[2])) if a_ != b_)
                outcome[k] += 1
                undo_a.append(i)
        bar_int.append(bi); bar_notes.append(bn)
        for name, undo in (("cf_undo_drops", undo_d), ("cf_undo_alts", undo_a), ("cf_undo_all", undo_d + undo_a)):
            cp = inotes_from(src, d["labels"])
            for i in undo:
                pc, o, re = d["info"][i]["top"]
                cp[i].part, cp[i].octave, cp[i].real = pc, A.OCTAVES[o], re
            cf[name].append(make_record(r, name, regime, ens, A.expand(cp)))
    bi, bn = np.concatenate(bar_int), np.concatenate(bar_notes)
    order = np.argsort(-bi)
    conc = {}
    for q in (0.1, 0.2):
        m = max(1, int(len(bi) * q))
        conc[f"top{int(q * 100)}pct_bars"] = {"share_interventions": float(bi[order[:m]].sum() / max(1, bi.sum())),
                                              "share_notes": float(bn[order[:m]].sum() / max(1, bn.sum()))}
    n = res["n_notes"]
    res.update({
        "reproduces_stored_records": f"{reproduced}/{reproduced + mism}",
        "intervention_rate": res["n_intervened"] / n,
        "drop_rate": sum(tier_drop.values()) / n,
        "drop_rate_from_interventions": outcome["drop"] / n,
        "drop_rate_model_chosen": res["n_top_drop"] / n,
        "blocking_checks_share": {k: v / res["n_intervened"] for k, v in blocked.most_common()},
        "outcome_share": {k: v / res["n_intervened"] for k, v in outcome.most_common()},
        "intervention_rate_by_source_polyphony": {str(k): by_poly[k] / by_poly_n[k] for k in sorted(by_poly_n)},
        "notes_by_source_polyphony": {str(k): by_poly_n[k] / n for k in sorted(by_poly_n)},
        "concentration": conc,
        "drop_rate_by_tier": {t: tier_drop[t] / tier_n[t] for t in ("top", "inner", "bass")},
        "intervention_drop_rate_by_tier": {t: tier_drop_int[t] / tier_n[t] for t in ("top", "inner", "bass")},
        "notes_by_tier": {t: tier_n[t] / n for t in ("top", "inner", "bass")},
        "drop_rate_by_source_part": {SRC_NAMES[s]: sp_drop[s] / sp_n[s] for s in sorted(sp_n)},
        "intervention_drop_rate_by_source_part": {SRC_NAMES[s]: sp_drop_int[s] / sp_n[s] for s in sorted(sp_n)},
    })
    return res, cf



def retention_by_tier(src, out_notes, tiers):
    """Share of source notes reproduced (same pitch, onset within a 16th, any part), per voice tier."""
    by = defaultdict(list)
    for _, o, d, x in out_notes:
        by[x].append(o)
    kept, n = Counter(), Counter()
    for (sp, o, d, x), t in zip(src, tiers):
        n[t] += 1
        if any(abs(o - y) < F(1, 4) for y in by.get(x, ())):
            kept[t] += 1
    return kept, n


def _harness(paths, od, workers):
    from arrangement.eval.harness import run
    done = Path(od) / "run.json"
    if not (done.exists() and done.stat().st_mtime > max(Path(p).stat().st_mtime for p in paths)):
        run([str(p) for p in paths], od, workers=workers, soft=False)
    m = defaultdict(list)
    for line in open(Path(od) / "metrics.jsonl"):
        x = json.loads(line)
        m[x["system"]].append(x)
    return m


def _pooled(rows):
    from decoding.gate import _stats
    rows = sorted(rows, key=lambda r: r["input_id"])
    s = _stats(rows)
    fid = {k: float(sm.sum() / c.sum()) for k, (sm, c) in s["fid"].items()}
    mt = [(r["fidelity"]["vs_source"]["mel_top_f1__sum"], r["fidelity"]["vs_source"]["mel_top_f1__n_segments"])
          for r in rows]
    fid["mel_top_f1"] = sum(a for a, _ in mt) / sum(b for _, b in mt)
    rates = 100 * s["viol"].sum(0) / s["notes"].sum()
    return {"D": float(rates.max()), "n_out_notes": int(s["notes"].sum()), **fid}


def cmd_report(a):
    from arrangement.eval.record import load as load_recs
    report = {}
    md = ["# Block 4, Step 1 diagnostics (read-only; checker-v4, METRICS 1.3.0-draft)\n"]
    for regime in ("trio", "duo", "quartet"):
        base = base_records(regime)
        ens = load_ensemble(regime)
        by = {r.input_id: r for r in base}
        rd = OUT / "records"
        labs_cpu = pickle.load(open(OUT / f"oracle_cpu_labels__{regime}.pkl", "rb"))
        paths = [rd / f"{sy}__{regime}.jsonl" for sy in ("oracle", "oracle_mask_drop", "oracle_mask_repair")]
        R = {"cpu_stats": json.loads((OUT / f"oracle_cpu_stats__{regime}.json").read_text())}
        dec_o = load_decode("oracle", regime) if regime != "quartet" else {}
        dec_a = load_decode("arranger", regime) if regime != "quartet" else {}
        if dec_o and not (rd / f"oracle_mask_model__{regime}.jsonl").exists():
            save([make_record(by[k], "oracle_mask_model", regime, ens,
                              A.expand(inotes_from(sorted_source(by[k]), dec_o[k]["labels"]))) for k in sorted(dec_o)],
                 rd / f"oracle_mask_model__{regime}.jsonl")
        if dec_o:
            paths.append(rd / f"oracle_mask_model__{regime}.jsonl")
        cf = {}
        if dec_a:
            stored = {r.input_id: [tuple(n) for n in r.output.notes]
                      for r in load_recs(RUN / "records" / f"arranger_masked__{regime}.jsonl")}
            R["interventions_arranger_masked"], cf = analyse_interventions(regime, base, dec_a, stored)
            for name, recs in cf.items():
                if not (rd / f"{name}__{regime}.jsonl").exists():
                    save(recs, rd / f"{name}__{regime}.jsonl")
        cf_paths = [rd / f"{name}__{regime}.jsonl" for name in cf]
        if dec_o:
            R["interventions_oracle_mask_model"], _ = analyse_interventions(regime, base, dec_o)
        M = _harness(paths, OUT / "harness" / regime, a.workers)
        if cf:   # counterfactuals scored separately, so a fix to them does not re-score the rest
            for sy, rows in _harness(cf_paths, OUT / "harness" / f"{regime}_cf", a.workers).items():
                M[sy] = rows
        if regime != "quartet":   # the existing Step 5 rows, same frozen harness
            for line in open(RUN / "eval" / regime / "harness" / "metrics.jsonl"):
                x = json.loads(line)
                M[x["system"]].append(x)
        R["pooled"] = {sy: _pooled(rows) for sy, rows in M.items() if sy != "amt"}
        # 1b: double-stop provenance + per-tier retention
        ds, ret = {}, {}
        label_sets = {"oracle": {k: v["oracle"] for k, v in labs_cpu.items()},
                      "oracle_mask_drop": {k: v["drop"] for k, v in labs_cpu.items()}}
        if dec_o:
            label_sets["oracle_mask_model"] = {k: v["labels"] for k, v in dec_o.items()}
        if dec_a:
            label_sets["arranger_masked"] = {k: v["labels"] for k, v in dec_a.items()}
        jobs = [(regime, r, {sy: L[r.input_id] for sy, L in label_sets.items()}) for r in base]
        with Pool(a.workers) as pool:
            per = pool.map(_ds_job, jobs, chunksize=1)
        for sy in label_sets:
            cls, byp, kept, n, nout = Counter(), Counter(), Counter(), Counter(), 0
            for x in per:
                no, c, bp, k_, n_ = x[sy]
                nout += no; cls.update(c); byp.update(bp); kept.update(k_); n.update(n_)
            ds[sy] = {"per_100_out_notes": {c: 100 * v / nout for c, v in cls.items()},
                      "share": {c: v / max(1, sum(cls.values())) for c, v in cls.items()},
                      "by_part": {f"{ens.part_names[p]}:{c}": v for (p, c), v in sorted(byp.items())}}
            ret[sy] = {t: kept[t] / n[t] for t in ("top", "inner", "bass")}
        R["double_stops"], R["retention_by_tier"] = ds, ret
        report[regime] = R
        (OUT / f"report__{regime}.json").write_text(json.dumps(R, indent=1, default=str))
        print("done", regime, flush=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps(report, indent=1, default=str)[:20000])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["decode", "cpu", "report"])
    ap.add_argument("--regime", default="trio")
    ap.add_argument("--mode", default="arranger", choices=["arranger", "oracle"])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    {"decode": cmd_decode, "cpu": cmd_cpu, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
