"""Write HEADROOM.md from results/summary.json (every number in it is computed
here) plus the hand-written interpretation in headroom/interpretation.md.

    python -m headroom.report
"""
from __future__ import annotations

import json
from pathlib import Path

from arrangement.checker import CHECKS

HEAD = Path(__file__).resolve().parent
ROOT = HEAD.parent
RES = HEAD / "results"
REGIME_NAME = {"quartet": "String quartet (Vn Vn Va Vc)", "trio": "String trio (Vn Va Vc), baseline",
               "duo": "Vn + Vc duo", "solo_violin": "Solo violin", "solo_flute": "Solo flute (monophonic)",
               "piano": "Solo piano (hand span)"}
SYS_NAME = {"ou_band": "Ou et al. band arranger (neural)", "ou_piano": "Ou et al. piano arranger (neural)",
            "amt": "Anticipatory Music Transformer (secondary; generation)", "continuity": "Continuity (rule-based)",
            "naive": "Naive (rule-based)", "ou_band_dedup": "Ou et al. band, duplicates collapsed (sensitivity)",
            "ou_piano_dedup": "Ou et al. piano, duplicates collapsed (sensitivity)",
            "amt_dedup": "AMT, duplicates collapsed (sensitivity)", "control": "Random control", "floor": "Published scores (floor)"}
SYS_ORDER = ["ou_band", "ou_band_dedup", "ou_piano", "ou_piano_dedup", "amt", "amt_dedup", "continuity", "naive", "control", "floor"]
ABBR = {"simultaneity": "simult.", "range": "range", "chord_size": "chord", "hand_span": "span", "transition": "trans."}


def f(x, d=3):
    return "–" if x is None else f"{x:.{d}f}"


def ci(c):
    return f"[{c[0]:.2f}, {c[1]:.2f}]"


def main() -> None:
    J = json.loads((RES / "summary.json").read_text())
    S, B = J["summary"], J["baseline"]
    L = ["# HEADROOM: how often do existing arrangement systems produce unplayable output?", ""]
    L += ["> **Systems measured:** Ou et al. (NeurIPS 2025, released weights) is the primary, neural system and",
          "> drives the decision. The rule-based assigners are reported alongside and labelled \"rule-based\"",
          "> everywhere; their numbers are headroom against rule-based systems only. The Anticipatory Music",
          "> Transformer is secondary (generation, not arrangement) and never decides.", ""]
    L += ["## Decision (pre-registered rule, DECISION.md + amendment A1)", "",
          f"- Baseline regime: string trio. Primary system: {SYS_NAME[B['system']]}.",
          f"- **D = {B['D']:.2f} violations per 100 notes** (worst single check: `{B['D_check']}`), "
          f"95% score-bootstrap CI **{ci(B['D_ci95'])}**.",
          f"- Threshold band of the CI: **{B['band']}**. Positive control CI {ci(B['control_D_ci95'])} "
          f"({'valid: entirely above 5' if B['control_valid'] else 'INVALID: not entirely above 5'}). "
          f"Sparse: {'yes' if B['sparse'] else 'no'}.",
          f"- **Verdict: {B['verdict']}.**", ""]
    interp = HEAD / "interpretation.md"
    if interp.exists():
        L += [interp.read_text().strip(), ""]
    L += ["## Evaluation set and pairing", "",
          f"- {J['n_movements']} movements: seeded random sample (seed 0) of the 626 non-dev OpenScore string-quartet",
          "  movements (`headroom/data/eval_set.json`). None was used for assigner tuning or transition",
          "  calibration; upper ranges were fitted on the full corpus, so source pitches lie inside the string ranges.",
          "- **FROM:** the full four-part quartet (grace notes dropped). **FOR:** the regime's ensemble. Every regime",
          "  except piano is a reduction.",
          "- Out of distribution for both neural systems (trained on Lakh MIDI, mostly pop). The claim is limited to",
          "  these systems on classical quartet sources.",
          f"- Checker: tag `{J['checker_tag']}` (code identical to `checker-v1`). Outputs present: "
          + ", ".join(f"{k} {v}/{J['n_movements']}" for k, v in J["outputs_present"].items()) + ".", ""]
    L += ["## Sweep: D per regime and system", "", "![sweep](headroom/results/sweep.png)", "",
          "| Regime | System | D | 95% CI | worst check | verdict band |", "|---|---|---|---|---|---|"]
    for r, g in S.items():
        for s in SYS_ORDER:
            if s in g:
                x = g[s]
                band = J["sweep"].get(r, {}).get("band", "") if s in ("ou_band", "ou_piano") else ""
                L.append(f"| {REGIME_NAME[r]} | {SYS_NAME[s]} | {x['D']:.3f} | {ci(x['D_ci95'])} | {x['D_check']} | {band} |")
    L += ["", "Bands are given for the primary system only; non-baseline bands are secondary findings (DECISION.md).", ""]
    L += ["## Per check type (never summed): violations per 100 output notes, with 95% CI", ""]
    head = "| Regime | System | " + " | ".join(ABBR[c] for c in CHECKS) + " |"
    L += [head, "|---|---|" + "---|" * len(CHECKS)]
    for r, g in S.items():
        for s in SYS_ORDER:
            if s in g:
                cells = [f"{g[s]['checks'][c]['per_100']:.3f} {ci(g[s]['checks'][c]['ci95'])}" for c in CHECKS]
                L.append(f"| {r} | {s} | " + " | ".join(cells) + " |")
    L += ["", "Simultaneity applies only to monophonic instruments (flute) and hand span only to keyboard (piano);",
          "elsewhere they are 0 by construction. Transition is off for flute and piano (A1.4).", ""]
    L += ["## Note counts against the source (sparsity guard, A1.6)", "",
          "Retention per target part = output notes in that part / notes of its reference source part (violin → Vn1,",
          "viola → Va, cello → Vc, flute → Vn1, piano → all four parts). Sparse = any part below 0.8.", "",
          "| Regime | System | output notes | source notes | total retention | per-part retention | sparse | off-ensemble notes | bars truncated |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r, g in S.items():
        for s in SYS_ORDER:
            if s in g:
                x = g[s]
                L.append(f"| {r} | {s} | {x['n_out_notes']:,} | {x['n_source_notes']:,} | {x['retention_total_vs_source']:.2f} | "
                         f"{', '.join(f'{v:.2f}' for v in x['retention_per_part'])} | {'yes' if x['sparse'] else 'no'} | "
                         f"{x.get('n_off_ensemble', '')} | {x.get('bars_truncated', '') if x.get('bars_truncated') is not None else ''} |")
    L += ["", "Rule-based systems and the control assign every source note, so their total retention is 1 and their",
          "per-part retention only shows how they spread notes. Retention matters for the neural systems. AMT is",
          "compared with the same 32-bar window of the source.", ""]
    L += ["## Per-score distribution of the primary system (is the rate driven by a few pieces?)", "",
          "| Regime | System | check | scores with any | median per score | p90 | max | share in worst 5% | worst movements |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r, g in S.items():
        for s in ("ou_band", "ou_piano", "amt"):
            if s not in g:
                continue
            for c in CHECKS:
                x = g[s]["checks"][c]
                if not x["violations"]:
                    continue
                ps = x["per_score"]
                worst = "; ".join(f"{w['key'][:40]}… ({w['per_100']:.1f})" for w in x["worst"])
                L.append(f"| {r} | {s} | {c} | {ps['scores_with_any']} | {ps['median']:.2f} | {ps['p90']:.2f} | {ps['max']:.2f} | "
                         f"{f(x['top5pct_share'], 2)} | {worst} |")
    L += ["", "## Where the primary system's violations are (by part; range split by direction)", ""]
    for r, g in S.items():
        for s in ("ou_band", "ou_piano"):
            if s in g:
                L.append(f"- **{r} / {s}:** by check:part {g[s]['violations_by_check_part']}; "
                         f"range by direction:part {g[s]['range_by_direction_part']}")
    L += ["", "## Reproduce", "", "    headroom/run_all.sh", "",
          "Steps: export sources (checker env) → generate (model env, `headroom/env.md`) → measure, figure, report",
          "(checker env). Raw per-score results: `headroom/results/per_score.csv`; pooled statistics:",
          "`headroom/results/summary.json`; raw model outputs: `headroom/data/out/` (archived as",
          "`headroom/results/outputs.tar.gz`).", ""]
    (ROOT / "HEADROOM.md").write_text("\n".join(L))
    print(ROOT / "HEADROOM.md")


if __name__ == "__main__":
    main()
