"""Sweep figure: decision statistic D (worst single check, per 100 notes) with
95% score-bootstrap CI, per regime and system. Reads results/summary.json.

    python -m headroom.figure
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RES = Path(__file__).resolve().parent / "results"
ORDER = ["quartet", "trio", "duo", "solo_violin", "solo_flute", "piano"]
LABEL = {"quartet": "String\nquartet", "trio": "String trio\n(baseline)", "duo": "Vn + Vc\nduo",
         "solo_violin": "Solo\nviolin", "solo_flute": "Solo flute\n(monophonic)", "piano": "Solo piano\n(hand span)"}
# fixed categorical order (validated: dataviz palette slots 1-4, light surface)
SERIES = [("neural", "Ou et al. (neural)", "#2a78d6", "o"),
          ("continuity", "Continuity (rule-based)", "#1baf7a", "s"),
          ("naive", "Naive (rule-based)", "#eda100", "^"),
          ("control", "Random control", "#eb6834", "D")]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def main() -> None:
    S = json.loads((RES / "summary.json").read_text())["summary"]
    fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    xs = {r: i + (0.6 if r == "piano" else 0) for i, r in enumerate(ORDER)}
    offs = {"neural": -0.18, "continuity": -0.06, "naive": 0.06, "control": 0.18}
    for key, label, color, marker in SERIES:
        pts = []
        for r in ORDER:
            g = S.get(r, {})
            sysname = ("ou_piano" if r == "piano" else "ou_band") if key == "neural" else key
            if sysname in g:
                pts.append((xs[r] + offs[key], g[sysname]))
        if not pts:
            continue
        x = [p[0] for p in pts]
        y = [max(p[1]["D"], 1e-3) for p in pts]
        lo = [max(p[1]["D_ci95"][0], 1e-3) for p in pts]
        hi = [max(p[1]["D_ci95"][1], 1e-3) for p in pts]
        ax.vlines(x, lo, hi, colors=color, linewidths=2, linestyles="solid", zorder=2)
        ax.plot(x, y, marker=marker, ls="none", color=color, ms=7, mec=SURFACE, mew=1.5, label=label, zorder=3)
    if "floor" in S.get("quartet", {}):
        f = S["quartet"]["floor"]
        ax.plot([xs["quartet"]], [max(f["D"], 1e-3)], marker="*", ms=11, color=INK, mec=SURFACE, ls="none",
                label="Published scores (floor)", zorder=4)
    for t, txt in ((1, "1  (Pivot below)"), (5, "5  (Proceed above)")):
        ax.axhline(t, color=INK2, lw=1, ls=(0, (4, 3)), zorder=1)
        ax.text(1.01, t, txt, va="center", ha="left", fontsize=8, color=INK2, transform=ax.get_yaxis_transform())
    ax.axvline(len(ORDER) - 1 - 0.2, color=GRID, lw=1, zorder=0)
    ax.set_yscale("log")
    ax.set_ylim(1e-3, 400)
    ax.set_xlim(-0.5, len(ORDER) + 0.05)
    ax.set_xticks([xs[r] for r in ORDER])
    ax.set_xticklabels([LABEL[r] for r in ORDER], fontsize=8.5, color=INK)
    ax.set_ylabel("D = worst single check, violations per 100 notes (log)", fontsize=9, color=INK)
    ax.text(0, -0.24, "Tighter constraints →", transform=ax.transAxes, fontsize=8, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.set_title("Headroom against constraint tightness (95% CI over 150 movements; points below 0.001 drawn at 0.001)",
                 fontsize=9.5, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(RES / "sweep.png", facecolor=SURFACE)
    print(RES / "sweep.png")


if __name__ == "__main__":
    main()
