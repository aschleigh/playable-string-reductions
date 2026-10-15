"""MOCK figures with FABRICATED numbers -- NOT RESULTS.

Draws the planned primary figure (playability vs fidelity) once per outcome of
the interpretation table, plus the tightness figure, so the plan can be
falsified before any model exists. Every number below is invented by hand.
Nothing here reads data.

    MPLCONFIGDIR=<scratch> .venv/bin/python mock_figures/make_mock_figures.py

Writes mock_figures/FABRICATED_*.png. See README.md and DISTINGUISHABILITY.md.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent

# Reference palette (dataviz skill, light mode). Three categorical slots: the
# all-pairs-safe cap for scatter-like charts. Rule-based reference is neutral
# gray. Critical red is used only for the fabricated-data warning.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_UNC, C_BLOCK, C_TRAIN, C_RULE = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"
WARN = "#e34948"

X_LABEL = "Hard violations per 100 notes, worst single check type  (← more playable)"
Y_LABEL = "Fidelity: Noteᵢ F1 vs reference (↑ better)"
X_NOTE = "x = ONE check type (the worst), never a sum across checks"
WEIGHTS = [0.0, 0.5, 1, 2, 4, 8]   # fabricated reward-weight sweep; 0 = unconstrained fine-tune


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def watermark(fig):
    fig.text(0.5, 0.5, "FABRICATED DATA — NOT RESULTS", fontsize=46, color=WARN, alpha=0.13,
             ha="center", va="center", rotation=28, weight="bold", zorder=0)
    fig.text(0.5, 0.995, "⚠ FABRICATED DATA — NOT RESULTS — every number is invented",
             ha="center", va="top", fontsize=11, weight="bold", color="white",
             bbox=dict(boxstyle="square,pad=0.35", fc=WARN, ec="none"))


def point(ax, x, y, xerr, yerr, color, marker, label, dx=0.15, dy=0.012, ha="left"):
    ax.errorbar([x], [y], xerr=[[xerr[0]], [xerr[1]]], yerr=[[yerr], [yerr]], fmt=marker, ms=9,
                color=color, mec=SURFACE, mew=2, ecolor=color, elinewidth=1.4, capsize=3, zorder=6)
    ax.annotate(label, (x, y), (x + dx, y + dy), fontsize=9, color=INK, ha=ha, zorder=5)


def curve(ax, xs, ys, yerr, label_weights=True, label="trained (reward-weight sweep)", lx=None, off=(0.6, 0.045)):
    ax.plot(xs, ys, "-", color=C_TRAIN, lw=2, zorder=3)
    ax.errorbar(xs, ys, yerr=yerr, fmt="D", ms=7, color=C_TRAIN, mec=SURFACE, mew=2,
                ecolor=C_TRAIN, elinewidth=1.2, capsize=2.5, zorder=4)
    if label_weights:
        for w, x, y in zip(WEIGHTS, xs, ys):
            ax.annotate(f"w={w:g}", (x, y), (x + 0.12, y - 0.028), fontsize=7.5, color=INK2, zorder=5)
    i = len(xs) // 2 if lx is None else lx
    ax.annotate(label, (xs[i], ys[i]), (xs[i] + off[0], ys[i] + off[1]), fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8), zorder=5)


def legend(ax, loc="lower right"):
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", color=C_UNC, ms=8, label="unconstrained model"),
         Line2D([], [], marker="s", ls="", color=C_BLOCK, ms=8, label="constrained decoding (blocking)"),
         Line2D([], [], marker="D", ls="-", color=C_TRAIN, ms=7, label="trained model (sweep)"),
         Line2D([], [], marker="^", ls="", color=C_RULE, ms=8, label="rule-based continuity (reference)")]
    ax.legend(handles=h, loc=loc, fontsize=8.5, frameon=True, facecolor=SURFACE, edgecolor=GRID)


# ---- fabricated numbers, trio baseline -------------------------------------
UNC = (5.1, 0.62)            # unconstrained: x loosely at HEADROOM's trio scale, y invented
UNC_XERR, YERR = (0.45, 0.45), 0.015
RULE = (0.17, 0.45)
OUTCOMES = {
    1: dict(slug="blocking_matches_training", title="Outcome 1: blocking matches training",
            block=0.585, xs=[5.1, 3.4, 2.0, 1.0, 0.45, 0.15], ys=[0.62, 0.612, 0.603, 0.596, 0.59, 0.588],
            note="Blocking and the trained curve's playable end overlap within CI.\n"
                 "Quality claim ('and quality') is NOT on this plot: needs the listener/performer study."),
    2: dict(slug="training_beats_blocking", title="Outcome 2: training beats blocking at the same playability",
            block=0.50, xs=[5.1, 3.4, 2.0, 1.0, 0.45, 0.10], ys=[0.62, 0.618, 0.614, 0.61, 0.606, 0.60],
            note="Gap read at the zero-violation end: trained 0.60 vs blocking 0.50.\n"
                 "Trained curve does not reach exactly 0; compare at matched rate (see DISTINGUISHABILITY.md)."),
    3: dict(slug="training_beats_blocking_blocking_degrades",
            title="Outcome 3: training beats blocking; blocking degrades as constraints tighten",
            block=0.50, xs=[5.1, 3.4, 2.0, 1.0, 0.45, 0.10], ys=[0.62, 0.618, 0.614, 0.61, 0.606, 0.60],
            note="At ONE tightness level this is pixel-identical to outcome 2.\n"
                 "Only the tightness figure (FABRICATED_tightness_gap.png) separates them.",
            block_off=(0.3, 0.005)),
    4: dict(slug="neither_improves", title="Outcome 4: neither improves on the unconstrained model",
            block=0.44, xs=[5.1, 4.6, 3.9, 2.6, 1.3, 0.35], ys=[0.62, 0.60, 0.565, 0.52, 0.48, 0.455],
            note="Both slide down to the rule-based point: playability is bought with fidelity,\n"
                 "and a rule-based assigner already sits there at no training cost.",
            off=(-2.3, 0.06)),
}


def outcome_figure(k: int, o: dict) -> Path:
    fig, ax = plt.subplots(figsize=(9.5, 6.4), facecolor=SURFACE)
    style(ax)
    point(ax, *UNC, UNC_XERR, YERR, C_UNC, "o", "unconstrained model\n(= trained at w=0)")
    point(ax, 0.0, o["block"], (0, 0), YERR, C_BLOCK, "s", "constrained decoding\n(blocking, exactly 0)",
          dx=o.get("block_off", (0.15, -0.045))[0], dy=o.get("block_off", (0.15, -0.045))[1])
    point(ax, *RULE, (0.04, 0.04), YERR, C_RULE, "^", "rule-based continuity", dx=0.2, dy=-0.03)
    curve(ax, o["xs"], o["ys"], YERR, off=o.get("off", (0.6, 0.045)))
    ax.set_xlim(-0.4, 6.2)
    ax.set_ylim(0.38, 0.70)
    ax.set_xlabel(X_LABEL, color=INK, fontsize=10)
    ax.set_ylabel(Y_LABEL, color=INK, fontsize=10)
    ax.set_title(f"MOCK: {o['title']}\nString trio (baseline regime)", color=INK, fontsize=12, loc="left")
    ax.text(0.01, 0.985, o["note"] + "\n" + X_NOTE + ".  Error bars: invented 95% CIs.",
            transform=ax.transAxes, fontsize=8.5, color=INK2, va="top")
    legend(ax)
    watermark(fig)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    p = OUT / f"FABRICATED_outcome{k}_{o['slug']}.png"
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return p


# ---- tightness figure ------------------------------------------------------
LEVELS = ["trio (baseline)", "Vn+Vc duo", "solo violin"]
UNC_X = [5.1, 8.2, 16.0]     # invented; scale mimics HEADROOM's Ou et al. D per regime
UNC_Y = [0.62, 0.56, 0.47]   # fidelity falls with tightness for everyone (fewer parts to hit)
TIGHT = {
    3: dict(name="Outcome 3: gap WIDENS (blocking degrades)", block=[0.50, 0.38, 0.22],
            train_end=[0.60, 0.53, 0.43]),
    2: dict(name="Outcome 2 (contrast): gap CONSTANT", block=[0.50, 0.44, 0.35],
            train_end=[0.60, 0.54, 0.45]),
}


def tightness_figure() -> Path:
    fig, axes = plt.subplots(2, 4, figsize=(16, 8.2), facecolor=SURFACE,
                             gridspec_kw=dict(width_ratios=[1, 1, 1, 0.9]))
    for r, (k, t) in enumerate(TIGHT.items()):
        for c, lev in enumerate(LEVELS):
            ax = axes[r, c]
            style(ax)
            ux, uy = UNC_X[c], UNC_Y[c]
            xs = [ux, ux * 0.6, ux * 0.35, ux * 0.15, ux * 0.06, 0.1]
            ys = [uy + (t["train_end"][c] - uy) * f for f in (0, 0.15, 0.35, 0.6, 0.85, 1.0)]
            ax.plot(xs, ys, "-D", color=C_TRAIN, ms=5, lw=1.8, mec=SURFACE, mew=1.5, zorder=3)
            ax.errorbar([ux], [uy], xerr=[[0.5], [0.5]], yerr=YERR, fmt="o", ms=8, color=C_UNC,
                        mec=SURFACE, mew=2, capsize=3, zorder=4)
            ax.errorbar([0], [t["block"][c]], yerr=YERR, fmt="s", ms=8, color=C_BLOCK, mec=SURFACE,
                        mew=2, capsize=3, zorder=4)
            gap = t["train_end"][c] - t["block"][c]
            ax.annotate("", (0.35, t["block"][c]), (0.35, t["train_end"][c]),
                        arrowprops=dict(arrowstyle="<->", color=INK, lw=1.1))
            ax.text(0.6, (t["block"][c] + t["train_end"][c]) / 2, f"gap {gap:+.2f}", fontsize=9,
                    color=INK, va="center")
            ax.set_xlim(-0.8, 17.5)
            ax.set_ylim(0.15, 0.70)
            if r == 0:
                ax.set_title(f"MOCK: {lev}", color=INK, fontsize=11, loc="left")
            if c == 0:
                ax.set_ylabel(f"{t['name']}\n\nNoteᵢ F1 (↑)", color=INK, fontsize=9.5)
            else:
                ax.set_yticklabels([])
            if r == 1:
                ax.set_xlabel("violations / 100 notes, worst check (←)", color=INK, fontsize=9)
        # gap panel: training minus blocking, per level. Own y scale (a different quantity; one axis).
        ax = axes[r, 3]
        style(ax)
        gaps = [a - b for a, b in zip(t["train_end"], t["block"])]
        ax.plot(range(3), gaps, "-o", color=INK, lw=2, ms=7, mec=SURFACE, mew=2)
        for i, g in enumerate(gaps):
            ax.annotate(f"{g:+.2f}", (i, g), (i, g + 0.012), fontsize=9, ha="center", color=INK)
        ax.set_xticks(range(3), ["trio", "duo", "solo Vn"])
        ax.set_xlim(-0.3, 2.3)
        ax.set_ylim(0, 0.26)
        ax.set_ylabel("trained − blocking, Noteᵢ F1", color=INK, fontsize=9)
        if r == 0:
            ax.set_title("MOCK: the gap per level", color=INK, fontsize=11, loc="left")
        if r == 1:
            ax.set_xlabel("constraint tightness →", color=INK, fontsize=9)
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", color=C_UNC, ms=8, label="unconstrained model"),
         Line2D([], [], marker="s", ls="", color=C_BLOCK, ms=8, label="constrained decoding (blocking)"),
         Line2D([], [], marker="D", ls="-", color=C_TRAIN, ms=6, label="trained model (reward-weight sweep)")]
    fig.legend(handles=h, loc="lower center", ncol=3, fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, 0.025))
    fig.text(0.01, 0.006, "Shared y across levels, but F1 is NOT on a common scale across ensembles "
             "(different references). Gap panel = within-level difference. " + X_NOTE + ".",
             fontsize=8.5, color=INK2)
    watermark(fig)
    fig.tight_layout(rect=(0, 0.07, 1, 0.955))
    p = OUT / "FABRICATED_tightness_gap.png"
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return p


def main() -> None:
    for k, o in OUTCOMES.items():
        print(outcome_figure(k, o))
    print(tightness_figure())


if __name__ == "__main__":
    main()
