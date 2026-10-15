"""Week summary (2026-10-12..15): the annotated results table and the double-stop figure, from the R46
confirmatory test (145 evaluation movements, checker-v5, melody-first decoding), plus real-quartet rates.

    python -m model.week_summary
Writes model/results/confirm/summary_table.md, summary_table.json and model/results/confirm/double_stops.png.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from arrangement.eval.record import load
from arrangement.eval.reduction import _sounding_sets, voice_tiers

ROOT = Path(__file__).resolve().parents[1]
CF = ROOT / "model" / "results" / "confirm"
REC = ROOT / "headroom" / "data" / "records"
REVIEW_IDX = (22, 67, 39, 42, 148)
SYSTEMS = [  # (row label, system name in the confirm harness, records file or None)
    ("Ou et al., masked", "ou_band_masked", None),
    ("arranger-v2b, masked", "arranger-v2b_masked", "arranger-v2b"),
    ("control S, masked", "control-S_masked", "control-S"),
    ("control-S2, masked", "control-S2_masked", "control-S2"),
]


def ds_moments(notes):
    ns = sorted(n for n in notes if n[1] > 0)
    cnt, active, k = 0, [], 0
    for t in sorted({n[0] for n in ns}):
        while k < len(ns) and ns[k][0] <= t:
            active.append(ns[k]); k += 1
        active = [n for n in active if n[0] + n[1] > t]
        cnt += len(active) >= 2
    return cnt


def real_rates():
    by = defaultdict(lambda: [0, 0])
    for line in open(ROOT / "model" / "data" / "train.jsonl"):
        d = json.loads(line)
        parts = defaultdict(list)
        for p, o, du, x in d["notes"]:
            parts[int(p)].append((F(o), F(du), int(x)))
        for p, ns in parts.items():
            inst = {0: "violin", 1: "violin", 2: "viola", 3: "cello"}[p]
            by[inst][0] += ds_moments(ns); by[inst][1] += len(ns)
            by[["Vn1", "Vn2", "Va", "Vc"][p]][0] += ds_moments(ns); by[["Vn1", "Vn2", "Va", "Vc"][p]][1] += len(ns)
    return {k: 100 * a / b for k, (a, b) in by.items()}


def melody_by_duration(rec):
    """Share of the source's top-voice duration kept (same pitch, onset within a 16th, any part)."""
    src = sorted([(p, F(o), F(d), x) for p, o, d, x in rec.source.notes if d > 0], key=lambda n: (n[1], n[3], n[2]))
    tiers = voice_tiers(src)
    by = defaultdict(list)
    for p, o, d, x in rec.output.notes:
        if d > 0:
            by[x].append(o)
    k = n = 0.0
    for (p, o, d, x), t in zip(src, tiers):
        if t != "top":
            continue
        n += float(d)
        k += float(d) * any(abs(o - y) < F(1, 4) for y in by.get(x, ()))
    return k, n


def main():
    rk = {json.loads((ROOT / "headroom" / "data" / "sources" / f"{i:03d}.json").read_text())["key"] for i in REVIEW_IDX}
    real = real_rates()
    out = {"real": real}
    md = []
    for regime in ("trio", "duo"):
        M = defaultdict(dict)
        for line in open(CF / "eval" / regime / "harness" / "metrics.jsonl"):
            m = json.loads(line)
            M[m["system"]][m["input_id"]] = m
        keys = sorted(set.intersection(*[set(M[s]) for _, s, _ in SYSTEMS]) - rk)
        rows = {}
        for label, sy, run in SYSTEMS:
            R = M[sy]
            recs = {r.input_id: r for r in load((CF / "eval" / regime / "records" / f"{sy}__{regime}.jsonl")
                                                if run else REC / f"{sy}__{regime}.jsonl")}
            row = {}
            red = lambda f: sum(R[k]["reduction"][f] for k in keys)
            row["melody_count"] = red("retention__top__kept") / red("retention__top__n")
            row["inner"] = red("retention__inner__kept") / red("retention__inner__n")
            kd = [melody_by_duration(recs[k]) for k in keys]
            row["melody_duration"] = sum(a for a, _ in kd) / sum(b for _, b in kd)
            fv = lambda f: (sum(R[k]["fidelity"]["vs_source"][f"{f}__sum"] for k in keys)
                            / sum(R[k]["fidelity"]["vs_source"][f"{f}__n_segments"] for k in keys))
            row["note_i_f1"] = fv("note_i_f1")
            row["harmony"] = (sum(R[k]["fidelity"]["vs_source"]["harmony__sum"] for k in keys)
                              / sum(R[k]["fidelity"]["vs_source"]["harmony__n_beats"] for k in keys))
            row["note_ratio"] = sum(R[k]["n_output_notes"] for k in keys) / sum(R[k]["n_source_notes"] for k in keys)
            nparts = len(recs[keys[0]].output.parts)
            per = [[0, 0] for _ in range(nparts)]
            for k in keys:
                by = defaultdict(list)
                for p, o, d, x in recs[k].output.notes:
                    by[p].append((o, d, x))
                for p in range(nparts):
                    per[p][0] += ds_moments(by.get(p, [])); per[p][1] += len(by.get(p, []))
            names = [pp.instrument for pp in recs[keys[0]].output.parts]
            row["ds"] = {names[p]: 100 * a / max(1, b) for p, (a, b) in enumerate(per)}
            if run:
                diag = {d["input_id"]: d for d in json.loads((CF / run / "records" / f"arranger_masked__{regime}.diag.json").read_text())}
                row["interventions"] = sum(diag[k]["masked_interventions"] for k in keys) / sum(diag[k]["n_in"] for k in keys)
                row["drops"] = sum(diag[k]["n_drop"] for k in keys) / sum(diag[k]["n_in"] for k in keys)
                U = M[sy.replace("_masked", "")]
                v = sum(sum(x for c, x in U[k]["playability"].items() if c.endswith("__violations") and isinstance(x, (int, float)))
                        for k in keys)
                row["unmasked_viol_per_100"] = 100 * v / sum(U[k]["n_output_notes"] for k in keys)
            rows[label] = row
        out[regime] = {"n_movements": len(keys), "rows": rows}
    (CF / "summary_table.json").write_text(json.dumps(out, indent=1))
    make_figure(out)
    print(json.dumps(out, indent=1)[:4000])


def make_figure(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
    series = [("Real quartets", None, "#c3c2b7"), ("arranger-v2b", "arranger-v2b, masked", "#2a78d6"),
              ("control S", "control S, masked", "#eb6834"), ("control-S2", "control-S2, masked", "#1baf7a")]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, facecolor=SURFACE,
                            gridspec_kw={"width_ratios": [3, 2]})
    real = out["real"]
    ymax = 0
    for ax, regime in zip(axs, ("trio", "duo")):
        rows = out[regime]["rows"]
        insts = list(rows["control-S2, masked"]["ds"])
        w = 0.19
        for si, (lab, rowname, col) in enumerate(series):
            for ii, inst in enumerate(insts):
                if rowname is None:
                    v = real["viola"] if (regime == "duo" and inst == "cello") else real[inst]
                else:
                    v = rows[rowname]["ds"][inst]
                ymax = max(ymax, v)
                x = ii + (si - 1.5) * (w + 0.02)
                ax.bar(x, v, width=w, color=col, edgecolor=SURFACE, linewidth=2, zorder=3)
                ax.text(x, v + 0.4, f"{v:.1f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
        ax.set_xticks(range(len(insts)))
        ax.set_xticklabels([i.capitalize() for i in insts], fontsize=10, color=INK)
        ax.set_title(f"{regime.capitalize()} ({out[regime]['n_movements']} evaluation movements)", loc="left",
                     fontsize=11, color=INK)
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#c3c2b7")
        ax.tick_params(colors=MUTED, labelsize=8)
    axs[0].set_ylabel("double stops per 100 notes", fontsize=9, color=INK2)
    axs[0].set_ylim(0, ymax * 1.15)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in series]
    fig.legend(handles, [s[0] for s in series], loc="upper right", ncol=4, frameon=False, fontsize=9,
               bbox_to_anchor=(0.99, 1.0))
    fig.suptitle("Double stops per output part: models against real quartet parts", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.text(0.01, 0.005, "Real quartets: training-split parts (violin = Vn1 and Vn2 pooled; duo cello compared with viola, "
             "since it carries viola material). Models: masked, melody-first decoding, checker-v5.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    fig.savefig(CF / "double_stops.png", dpi=160, facecolor=SURFACE)


if __name__ == "__main__":
    main()
