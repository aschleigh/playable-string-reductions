"""BLOCK6.md Step 5: the Block 6 confirmatory evaluation, criterion D (pre-registered in BLOCK6.md, R63; operational
form frozen in BLOCK6.md before any evaluation-set decode). checker-v6, METRICS 1.5.0-draft harness, melody-first
decoding, 145 evaluation movements (the 5 review movements excluded), paired 95% movement bootstrap (10,000, seed 0).
First confirmatory use of these movements for solo piano and solo flute; they were used for strings (R46, R56).

    python -m model.confirm6_eval --tested control-J

Per regime (piano, solo_flute), the tested system masked against Ou et al. masked (ou_piano_masked / ou_band_masked):
  1. hard violations: tested masked has 0; unmasked violations per 100 output notes, Δ (tested unmasked - Ou
     unconstrained) CI upper bound < 0;
  2. melody retention (top tier, count): Δ CI lower bound > 0;
  3. harmony: Δ CI lower bound > -0.02;
  4. interventions <= 5% of notes (point estimate);
  5. flute only: melody retention Δ (tested - top line) CI lower bound > -0.01.
Records: model/results/confirm6/<tested>/records (model/run_block6_c.sh). Writes model/results/confirm6/{eval.json, CONFIRM6.md}.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from arrangement.eval.harness import METRICS_VERSION, run as harness_run
from arrangement.eval.record import ArrangementRecord, load, make_score, save
from arrangement.eval.reduction import voice_tiers
from model.confirm_eval import N_BOOT, ci, ratio_boot, review_keys

ROOT = Path(__file__).resolve().parents[1]
C6 = ROOT / "model" / "results" / "confirm6"
REC = ROOT / "headroom" / "data" / "records"
OU = {"piano": "ou_piano", "solo_flute": "ou_band"}


def top_line_records(regime):
    """The trivial flute baseline: the top-tier note at each onset, folded into C4-C7, cut at the next onset."""
    out = []
    for b in load(REC / f"naive__{regime}.jsonl"):
        src = sorted([(p, F(o), F(d), x) for p, o, d, x in b.source.notes if d > 0], key=lambda n: (n[1], n[3], n[2]))
        tiers = voice_tiers(src)
        tops = sorted((o, d, x) for (p, o, d, x), t in zip(src, tiers) if t == "top")
        notes = []
        for k, (o, d, x) in enumerate(tops):
            if notes and notes[-1][1] == o:
                continue
            while x < 60:
                x += 12
            while x > 96:
                x -= 12
            nxt = next((tops[j][0] for j in range(k + 1, len(tops)) if tops[j][0] > o), None)
            notes.append((0, o, min(d, nxt - o) if nxt is not None else d, x))
        out.append(ArrangementRecord(system="top_line", seed=None, input_id=b.input_id, ensemble=regime, source=b.source,
                                     output=make_score([("Flute", "flute")], notes), bars=b.bars,
                                     reference_source_parts=b.reference_source_parts, meta=b.meta))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tested", default="control-J")
    ap.add_argument("--regimes", nargs="+", default=["piano", "solo_flute"])   # R82: flute first, piano after its fix
    a = ap.parse_args()
    T = a.tested
    rk = review_keys()
    res = {"metrics_version": METRICS_VERSION, "tested": T, "checker": "checker-v6", "excluded_review_movements": sorted(rk),
           "caveat": "first confirmatory use for piano and flute; the movements were used twice for strings (R46, R56)"}
    md = [f"# Block 6 confirmatory test: {T}, solo piano and solo flute (criterion D)\n\n"
          f"checker-v6, METRICS {METRICS_VERSION}, melody-first decoding, 145 evaluation movements (5 review movements "
          "excluded), paired 95% movement bootstrap. First confirmatory use for piano and flute; the movements were used "
          "for strings (R46, R56).\n"]
    for regime in a.regimes:
        od = C6 / "eval" / regime
        (od / "records").mkdir(parents=True, exist_ok=True)
        rd = C6 / T / "records"
        paths, diags = [], {}
        for sy, name in (("arranger", T), ("arranger_masked", T + "_masked")):
            rs = load(rd / f"{sy}__{regime}.jsonl")
            for r in rs:
                object.__setattr__(r, "system", name)
            save(rs, od / "records" / f"{name}__{regime}.jsonl")
            paths.append(od / "records" / f"{name}__{regime}.jsonl")
            diags[name] = {d["input_id"]: d for d in json.loads((rd / f"{sy}__{regime}.diag.json").read_text())}
        ou_m, ou_u = f"{OU[regime]}_masked", OU[regime]
        paths += [REC / f"{ou_m}__{regime}.jsonl", REC / f"{ou_u}__{regime}.jsonl", REC / f"naive__{regime}.jsonl"]
        if regime == "solo_flute":
            save(top_line_records(regime), od / "records" / f"top_line__{regime}.jsonl")
            paths.append(od / "records" / f"top_line__{regime}.jsonl")
        harness_run([str(p) for p in paths], od / "harness", workers=16, soft=False)
        M = defaultdict(dict)
        for line in open(od / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            M[m["system"]][m["input_id"]] = m
        keys = sorted(set.intersection(*[set(v) for v in M.values()]) - rk)
        idx = np.random.default_rng(0).integers(0, len(keys), (N_BOOT, len(keys)))

        def ret(R, t):
            return (np.array([R[k]["reduction"][f"retention__{t}__kept"] for k in keys], float),
                    np.array([R[k]["reduction"][f"retention__{t}__n"] for k in keys], float))

        def harm(R):
            vs = [R[k]["fidelity"]["vs_source"] for k in keys]
            return np.array([v["harmony__sum"] for v in vs], float), np.array([v["harmony__n_beats"] for v in vs], float)

        def viol(R):
            v = np.array([sum(x for c, x in R[k]["playability"].items() if c.endswith("__violations") and isinstance(x, (int, float)))
                          for k in keys], float)
            return 100 * v, np.array([R[k]["n_output_notes"] for k in keys], float)

        def nr(R):
            return np.array([R[k]["n_output_notes"] for k in keys], float), np.array([R[k]["n_source_notes"] for k in keys], float)

        def paired(x, y):
            (an, ad), (bn, bd) = x, y
            ba, bb = ratio_boot(an, ad, idx), ratio_boot(bn, bd, idx)
            return {"run": float(an.sum() / ad.sum()), "ref": float(bn.sum() / bd.sum()),
                    "delta": float(an.sum() / ad.sum() - bn.sum() / bd.sum()), "ci95": ci(ba - bb)}

        X, Y, U, Xu = M[T + "_masked"], M[ou_m], M[ou_u], M[T]
        D = {"melody": paired(ret(X, "top"), ret(Y, "top")), "bass": paired(ret(X, "bass"), ret(Y, "bass")),
             "inner": paired(ret(X, "inner"), ret(Y, "inner")), "harmony": paired(harm(X), harm(Y)),
             "note_ratio": paired(nr(X), nr(Y)),
             "unmasked_viol_per_100": paired(viol(Xu), viol(U))}
        iv = sum(diags[T + "_masked"][k]["masked_interventions"] for k in keys) / sum(diags[T + "_masked"][k]["n_in"] for k in keys)
        hard_masked = float(viol(X)[0].sum() / 100)
        crit = {"1_hard_violations": hard_masked == 0 and D["unmasked_viol_per_100"]["ci95"][1] < 0,
                "2_melody_up": D["melody"]["ci95"][0] > 0,
                "3_harmony_noninferior": D["harmony"]["ci95"][0] > -0.02,
                "4_interventions_le_5pct": iv <= 0.05}
        if regime == "solo_flute":
            D["melody_vs_top_line"] = paired(ret(X, "top"), ret(M["top_line"], "top"))
            crit["5_not_worse_than_top_line"] = D["melody_vs_top_line"]["ci95"][0] > -0.01
        res[regime] = {"n_movements": len(keys), "paired_vs_ou_masked": D, "interventions": iv,
                       "hard_violations_masked": hard_masked, "criterion_D": crit, "criterion_D_holds": all(crit.values())}
        md.append(f"\n## {regime} ({len(keys)} movements): criterion D = {all(crit.values())}\n\n"
                  f"| {T} masked vs {ou_m} | reference | {T} | Δ [95% CI] |\n|---|---|---|---|\n")
        for k, v in D.items():
            md.append(f"| {k} | {v['ref']:.3f} | {v['run']:.3f} | {v['delta']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] |\n")
        md.append(f"\nInterventions {iv:.3f}; hard violations (masked) {hard_masked:.0f}.\n\n| Criterion D | Holds |\n|---|---|\n"
                  + "".join(f"| {k} | {v} |\n" for k, v in crit.items()))
    C6.mkdir(parents=True, exist_ok=True)
    tag = "" if a.regimes == ["piano", "solo_flute"] else "_" + "_".join(a.regimes)
    (C6 / f"eval{tag}.json").write_text(json.dumps(res, indent=1))
    (C6 / f"CONFIRM6{tag}.md").write_text("".join(md))
    print("".join(md))


if __name__ == "__main__":
    main()
